"""
agent/nodes.py
==============
5 Node xử lý suy luận của LangGraph Agentic RAG.

Sơ đồ luồng dữ liệu:
    classify_intent → search_knowledge → check_context
                                              │
                          ┌───────────────────┼──────────────────┐
                     (retry ≤ 3)         (context OK)      (no context/other)
                          │                   │                   │
                    search_knowledge    generate_answer     fallback_answer
                                              │                   │
                                             END                 END

Node trả về dict — LangGraph merge vào state hiện tại (không phải replace toàn bộ).
Pattern: return {**state, 'field_updated': new_value}

Hàm route_after_check() KHÔNG phải Node — đây là Conditional Edge function,
nhận state và trả về string key để LangGraph biết chuyển sang node nào.

LLM Integration:
    Dùng llm.get_chat_provider() để lấy provider từ DB.
    Các node là sync (LangGraph requirement) → dùng asyncio.run() để gọi async provider.
"""

import asyncio
import json
import logging
import re
import unicodedata
from typing import Any

from llm import get_chat_provider
from .state import (
    AdmissionState,
    MAX_SEARCH_ITERATIONS,
    MIN_CONTEXT_LENGTH,
    VALID_INTENTS,
    VALID_DOC_TYPES,
)
from .tools import search_admission_info

logger = logging.getLogger(__name__)

# Module-level event loop — được inject từ chat.py trước khi gọi asyncio.to_thread.
# Cho phép các node (chạy trong thread pool) gửi async coroutines
# vào main event loop của FastAPI mà không tạo loop mới — tránh xung đột asyncpg.
_MAIN_LOOP: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Inject FastAPI event loop vào module. Gọi 1 lần từ chat.py trước to_thread."""
    global _MAIN_LOOP
    _MAIN_LOOP = loop


def _run_async(coro):
    """
    Chạy async coroutine từ trong thread worker.

    Nếu _MAIN_LOOP đã được inject (FastAPI context) → dùng run_coroutine_threadsafe
    để gửi coroutine vào main loop. AsyncSession và asyncpg connection pool
    vẫn chạy trong đúng loop của chúng — không bị xung đột.

    Nếu không có _MAIN_LOOP (script CLI, test, ...) → fallback asyncio.run().
    """
    if _MAIN_LOOP is not None and _MAIN_LOOP.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, _MAIN_LOOP)
        return future.result()
    return asyncio.run(coro)


# ===========================================================================
# SYSTEM PROMPTS — Tập trung tại đây để dễ chỉnh sửa và version control
# ===========================================================================

_CLASSIFY_SYSTEM = """Phân tích câu hỏi tuyển sinh đại học và trả về JSON thuần túy (không thêm text nào khác).

Cấu trúc JSON bắt buộc:
{"intents": [...], "queries": [...], "filters": {"year": null, "doc_type": null}}

Giá trị hợp lệ:
- intents: mảng các giá trị trong ["check_score", "get_tuition", "get_scholarship", "get_major_info", "other"]
- doc_type: một trong ["diem_chuan", "hoc_phi", "chi_tieu", "quy_che", "thong_bao"] hoặc null. Khi hỏi về chỉ tiêu, số lượng, ngành đào tạo, danh sách ngành → dùng "chi_tieu". Nếu không chắc chắn → dùng null.
- year: số nguyên năm (ví dụ 2026) hoặc null
- queries: 1-3 cụm từ ngắn gọn tối ưu cho vector search

Quy tắc:
- Nếu câu hỏi không liên quan tuyển sinh: intents=["other"], queries=[câu hỏi gốc]
- Chỉ xuất JSON thuần túy, không giải thích, không bọc markdown

Ví dụ:
Câu hỏi: "Chỉ tiêu ngành CNTT năm 2026?"
Kết quả: {"intents":["get_major_info"],"queries":["chỉ tiêu ngành Công nghệ thông tin 2026"],"filters":{"year":2026,"doc_type":"chi_tieu"}}"""

_ANSWER_SYSTEM = """Bạn là Trợ lý ảo tư vấn tuyển sinh đại học chính thức của Trường Đại học Vinh.

NHIỆM VỤ: Trả lời câu hỏi thí sinh DỰA TRÊN DUY NHẤT thông tin có trong thẻ tài liệu trích xuất dưới đây.

QUY TẮC TUYỆT ĐỐI VÀ CHẶN ẢO GIÁC:
1. CHỈ sử dụng thông tin trong tài liệu trích xuất. Bất kỳ số liệu nào không có trong tài liệu trích xuất — dù bạn "biết" từ quá trình huấn luyện — TUYỆT ĐỐI KHÔNG đưa vào câu trả lời. Không tự bịa thêm ngành hoặc thông tin ngoài.
2. Nếu tài liệu trích xuất KHÔNG chứa thông tin cần thiết: Hãy trả lời lịch sự rằng không có thông tin này và hướng thí sinh liên hệ trực tiếp.
3. KHÔNG suy đoán, không tính toán suy ra từ dữ liệu khác, không bịa số liệu.
4. Mọi con số (điểm chuẩn, học phí, chỉ tiêu, mã ngành) phải xuất hiện NGUYÊN VẸN trong tài liệu trích xuất.
5. Trích dẫn nguồn tài liệu ở cuối câu trả lời (ví dụ: *Nguồn: Đề án tuyển sinh 2026, trang 4*).
6. Định dạng: ngắn gọn, cấu trúc rõ ràng. **In đậm** số liệu quan trọng.
7. Giọng văn: Thân thiện, lịch sự, mạnh mẽ — như cán bộ tư vấn tuyển sinh thực thụ.

QUY TẮC NGHIÊM NGẶT VỀ VIỆC LIỆT KÊ (CHỐNG LƯỜI BIẾNG):
1. Nếu người dùng hỏi về "danh sách", "các ngành", "những ngành nào", bạn BẮT BUỘC PHẢI LIỆT KÊ ĐẦY ĐỦ 100% tất cả các mục có trong tài liệu trích xuất.
2. TUYỆT ĐỐI KHÔNG ĐƯỢC dùng các cụm từ tóm tắt như "và các ngành khác", "vân vân", "bao gồm nhiều ngành".
3. Trình bày danh sách dưới dạng gạch đầu dòng rõ ràng. Nếu trong tài liệu trích xuất có 16 ngành, câu trả lời của bạn phải có đủ 16 gạch đầu dòng."""


# ===========================================================================
# NODE 1: classify_intent
# ===========================================================================

def classify_intent(state: AdmissionState) -> AdmissionState:
    """
    Node 1: Phân loại ý định và trích xuất bộ lọc từ câu hỏi thí sinh.

    Dùng LLM chat provider với JSON mode để ép buộc output là JSON hợp lệ.
    Provider được đọc từ DB slot "chat" — không hardcode Gemini.
    Fallback regex mạnh để xử lý các trường hợp model trả về JSON bọc markdown.

    Cập nhật state:
        intents, search_queries, dynamic_filters, iterations (reset về 0)
    """
    user_msg = state["user_message"]
    logger.info("[Node/Classify] ─── BẮT ĐẦU PHÂN LOẠI ───")
    logger.info("[Node/Classify] Câu hỏi: %r", user_msg)

    # Lấy provider từ DB và gọi JSON completion
    async def _call():
        import datetime
        current_year = datetime.datetime.now().year
        system_prompt = _CLASSIFY_SYSTEM + f"\n\nLưu ý thời gian thực: Năm nay là {current_year}. Nếu người dùng dùng các từ như 'năm nay', 'hiện tại', hãy tự động hiểu là {current_year}, 'năm ngoái' là {current_year - 1}."
        
        provider = await get_chat_provider()
        return await provider.complete_json(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
        )

    raw_response = _run_async(_call())

    logger.debug("[Node/Classify] Raw response từ LLM:\n%s", raw_response)

    # Bóc tách JSON với chiến lược nhiều lớp
    parsed = _extract_json_robust(raw_response, context="classify_intent")

    # Chuẩn hóa và validate từng field
    intents       = _normalize_intents(parsed.get("intents", []))
    queries       = _normalize_queries(parsed.get("queries", []), fallback=user_msg)
    filters       = _normalize_filters(parsed.get("filters", {}))

    logger.info(
        "[Node/Classify] ─── KẾT QUẢ PHÂN LOẠI ───\n"
        "  Intents : %s\n"
        "  Queries : %s\n"
        "  Filters : %s",
        intents, queries, filters,
    )

    return {
        **state,
        "intents":         intents,
        "search_queries":  queries,
        "dynamic_filters": filters,
        "iterations":      0,        # Reset counter trước mỗi lượt hội thoại mới
    }


# ===========================================================================
# NODE 2: search_knowledge
# ===========================================================================

def _remove_accents(input_str: str) -> str:
    """Loại bỏ dấu tiếng Việt để so sánh không phân biệt dấu."""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def _get_top_k(intents: list[str], queries: list[str]) -> int:
    """
    Câu hỏi liệt kê → lấy nhiều chunks hơn
    Câu hỏi cụ thể  → top 5 là đủ
    """
    LIST_KEYWORDS = [
        'tất cả', 'các ngành', 'danh sách', 'liệt kê',
        'có những', 'bao gồm', 'ngành nào', 'đào tạo gì', 'bao nhiêu ngành', 'những ngành nào'
    ]
    query_text = _remove_accents(' '.join(queries).lower())
    unaccented_keywords = [_remove_accents(kw.lower()) for kw in LIST_KEYWORDS]
    
    is_list_query = any(kw in query_text for kw in unaccented_keywords)
    
    if is_list_query:
        return 20  # Lấy nhiều hơn để cover toàn bộ
    return 5      # Câu hỏi cụ thể, top 5 đủ


def search_knowledge(state: AdmissionState) -> AdmissionState:
    """
    Node 2: Thực thi tìm kiếm vector search trên Qdrant.

    Với mỗi query trong search_queries:
        1. Gọi search_admission_info() với dynamic_filters
        2. Gộp tất cả kết quả
        3. Sắp xếp theo score giảm dần
        4. Deduplicate theo 80 ký tự đầu của content (fingerprint)
        5. Lấy top-5 chunks chất lượng nhất
        6. Format thành context string có kèm metadata nguồn

    Cập nhật state: search_results, context
    """
    queries  = state["search_queries"]
    base_filters = {
        k: v
        for k, v in state["dynamic_filters"].items()
        if k in {"year", "doc_type"} and v is not None
    }
    iteration = state["iterations"]

    if iteration == 0:
        active_filters = base_filters
    elif iteration == 1:
        active_filters = {
            k: v for k, v in base_filters.items()
            if k == "year"
        }
        logger.info("[Node/Search] Retry %d: bỏ doc_type filter", iteration)
    else:
        active_filters = {}
        logger.info("[Node/Search] Retry %d: search không filter", iteration)

    logger.info(
        "[Node/Search] ─── BẮT ĐẦU TÌM KIẾM (lần %d) ───\n"
        "  Số queries: %d | Active filters: %s",
        iteration + 1,
        len(queries),
        active_filters or "none",
    )

    # --- Xác định top_k dựa vào loại câu hỏi ---
    top_k = _get_top_k(state["intents"], queries)

    # --- Gom kết quả từ tất cả queries ---
    all_results: list[dict] = []
    for idx, query in enumerate(queries):
        logger.debug(
            "[Node/Search] Query %d/%d: %r", idx + 1, len(queries), query
        )
        partial = search_admission_info(query, filters=active_filters, top_k=top_k)
        all_results.extend(partial)
        logger.debug(
            "[Node/Search] Query %d trả về %d results.", idx + 1, len(partial)
        )

    # --- Deduplicate theo content fingerprint (80 ký tự đầu) ---
    seen_fingerprints: set[str] = set()
    unique_results: list[dict] = []

    # Sort theo score giảm dần TRƯỚC khi dedup — giữ lại bản score cao nhất
    for result in sorted(all_results, key=lambda x: x["score"], reverse=True):
        fingerprint = result["content"][:80].strip()
        if fingerprint and fingerprint not in seen_fingerprints:
            seen_fingerprints.add(fingerprint)
            unique_results.append(result)

    # Giới hạn top-k chunks chất lượng nhất
    top_results = unique_results[:top_k]

    logger.info(
        "[Node/Search] Kết quả: %d raw → %d unique → %d top được chọn.",
        len(all_results), len(unique_results), len(top_results),
    )

    # --- Format context string ---
    context_str = _format_context(top_results)

    return {
        **state,
        "relaxed_filters": active_filters,
        "search_results": top_results,
        "context":        context_str,
    }


# ===========================================================================
# NODE 3: check_context  (+ Conditional Edge Function)
# ===========================================================================

def check_context(state: AdmissionState) -> AdmissionState:
    """
    Node 3: Tăng bộ đếm vòng lặp.

    Node này chỉ chịu trách nhiệm MỘT VIỆC: tăng iterations.
    Quyết định định tuyến (retry/generate/fallback) được thực hiện
    bởi hàm route_after_check() trong add_conditional_edges.
    Thiết kế tách biệt này giúp mỗi thành phần có Single Responsibility.

    Cập nhật state: iterations (tăng thêm 1)
    """
    new_iteration = state["iterations"] + 1
    logger.info(
        "[Node/Check] Vòng lặp lần %d/%d | Context length: %d ký tự | Intents: %s",
        new_iteration,
        MAX_SEARCH_ITERATIONS,
        len(state["context"]),
        state["intents"],
    )
    return {**state, "iterations": new_iteration}


def route_after_check(state: AdmissionState) -> str:
    """
    Conditional Edge Function — Quyết định node tiếp theo sau check_context.

    KHÔNG phải Node — đây là hàm định tuyến của LangGraph.
    Nhận state hiện tại và trả về string key mapping sang node đích.

    Logic định tuyến (ưu tiên từ trên xuống dưới):

    ┌─────────────────────────────────────────────────────────────────────────┐
    │ RULE 1: Intent "other" → Fallback ngay (không search tiếp vô nghĩa)    │
    │         Vì: câu hỏi ngoài tuyển sinh sẽ không có data trong Qdrant     │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ RULE 2: Context đủ tốt → Generate answer                               │
    │         Điều kiện: len(context) >= MIN_CONTEXT_LENGTH (40 ký tự)       │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ RULE 3: Context thiếu + còn lượt retry → Retry search                  │
    │         Điều kiện: iterations < MAX_SEARCH_ITERATIONS (3)              │
    │         Chiến lược retry: node search sẽ dùng lại state hiện tại —    │
    │         trong thực tế có thể mở rộng để relax filters ở đây           │
    ├─────────────────────────────────────────────────────────────────────────┤
    │ RULE 4: Context thiếu + HẾT lượt retry → Fallback                      │
    │         Đã thử đủ 3 lần mà không có data → trả lời không biết         │
    └─────────────────────────────────────────────────────────────────────────┘

    Returns:
        "trigger_fallback"      → node `fallback`
        "trigger_generation"    → node `generate`
        "retry_search_loop"     → node `search` (quay vòng lặp)
    """
    intents    = state["intents"]
    context    = state["context"]
    iterations = state["iterations"]

    # --- RULE 1: Câu hỏi ngoài lề → Fallback ngay ---
    if intents == ["other"] or (len(intents) == 1 and "other" in intents):
        logger.info(
            "[Route] RULE 1 kích hoạt: intent='other' → trigger_fallback"
        )
        return "trigger_fallback"

    # --- RULE 2: Đã có context đủ → Generate ---
    context_length = len(context.strip())
    if context_length >= MIN_CONTEXT_LENGTH:
        logger.info(
            "[Route] RULE 2 kích hoạt: context=%d ký tự ≥ %d → trigger_generation",
            context_length, MIN_CONTEXT_LENGTH,
        )
        return "trigger_generation"

    # --- RULE 3: Context thiếu nhưng còn lượt retry ---
    if iterations < MAX_SEARCH_ITERATIONS:
        logger.warning(
            "[Route] RULE 3 kích hoạt: context=%d ký tự < %d | "
            "lần %d/%d → retry_search_loop",
            context_length, MIN_CONTEXT_LENGTH,
            iterations, MAX_SEARCH_ITERATIONS,
        )
        return "retry_search_loop"

    # --- RULE 4: Đã retry đủ số lần, vẫn thiếu context → Fallback ---
    logger.warning(
        "[Route] RULE 4 kích hoạt: Đã retry %d/%d lần, "
        "context vẫn < %d ký tự → trigger_fallback",
        iterations, MAX_SEARCH_ITERATIONS, MIN_CONTEXT_LENGTH,
    )
    return "trigger_fallback"


# ===========================================================================
# NODE 4: generate_answer
# ===========================================================================

def generate_answer(state: AdmissionState) -> AdmissionState:
    """
    Node 4: Sinh câu trả lời chính thức dựa trên context từ Qdrant.

    Xây dựng prompt = lịch sử hội thoại + câu hỏi mới (có bọc context).
    LLM sẽ trả lời dựa TRÊN DUY NHẤT nội dung trong thẻ tài liệu trích xuất.
    Provider được đọc từ DB slot "chat" — không hardcode Gemini.

    Cập nhật state: final_answer
    """
    context      = state["context"]
    user_message = state["user_message"]
    history      = state["history"]

    logger.info(
        "[Node/Generate] Sinh câu trả lời | context=%d ký tự | "
        "history=%d lượt",
        len(context), len(history),
    )

    # Prompt cuối: nhúng context vào câu hỏi user
    # Tách context khỏi history để tránh context contamination qua các lượt
    user_prompt_with_context = (
        f"=== TÀI LIỆU TRÍCH XUẤT ===\n{context}\n=== HẾT TÀI LIỆU ===\n\n"
        f"Câu hỏi của thí sinh: {user_message}"
    )

    # Ghép lịch sử + câu hỏi mới (context chỉ có ở lượt hiện tại)
    messages = list(history) + [{"role": "user", "content": user_prompt_with_context}]

    try:
        async def _call():
            import datetime
            current_year = datetime.datetime.now().year
            system_prompt = _ANSWER_SYSTEM + f"\n\nLưu ý: Thời điểm hiện tại là năm {current_year}. Nếu câu hỏi đề cập đến 'năm nay', hãy hiểu là {current_year}."
            provider = await get_chat_provider()
            return await provider.complete(
                messages=messages,
                system=system_prompt,
                max_tokens=2048,
                temperature=0.0,
                top_p=0.1,  # Nucleus sampling: chỉ chọn trong top-10% token xác suất cao
            )

        answer = _run_async(_call())
        logger.info(
            "[Node/Generate] Đã sinh câu trả lời (%d ký tự).", len(answer)
        )
    except Exception as e:
        logger.error(
            "[Node/Generate] Lỗi sinh câu trả lời: %s — chuyển fallback.", str(e)
        )
        answer = _static_fallback_message()

    return {**state, "final_answer": answer}


# ===========================================================================
# NODE 5: fallback_answer
# ===========================================================================

def fallback_answer(state: AdmissionState) -> AdmissionState:
    """
    Node 5: Trả lời dự phòng khi không tìm được thông tin liên quan.

    Kích hoạt khi:
    - Intent là "other" (câu hỏi ngoài lề tuyển sinh)
    - Đã retry đủ MAX_SEARCH_ITERATIONS lần mà context vẫn rỗng
    - Lỗi nghiêm trọng trong generate_answer

    Cập nhật state: final_answer
    """
    logger.info(
        "[Node/Fallback] Kích hoạt fallback | intents=%s | iterations=%d",
        state["intents"], state["iterations"],
    )

    # Cá nhân hóa fallback message theo loại intent
    intents = state["intents"]
    if "other" in intents:
        # Câu hỏi hoàn toàn ngoài lề
        message = (
            "Xin chào! Tôi là trợ lý tư vấn tuyển sinh của Trường Đại học Vinh. "
            "Câu hỏi của bạn có vẻ nằm ngoài phạm vi thông tin tuyển sinh mà tôi "
            "được đào tạo để hỗ trợ. 😊\n\n"
            "Bạn có thể hỏi tôi về:\n"
            "- 📊 Điểm chuẩn các ngành\n"
            "- 💰 Học phí và học bổng\n"
            "- 📋 Chỉ tiêu tuyển sinh\n"
            "- 📜 Quy chế và thủ tục xét tuyển\n\n"
            "Hoặc liên hệ trực tiếp: **Hội đồng Tuyển sinh ĐH Vinh** "
            "— 182 Lê Duẩn, TP. Vinh, Nghệ An."
        )
    else:
        # Câu hỏi đúng chủ đề nhưng không tìm được data
        message = _static_fallback_message()

    return {**state, "final_answer": message}


# ===========================================================================
# PRIVATE HELPERS
# ===========================================================================

def _extract_json_robust(text: str, context: str = "") -> dict:
    """
    Bóc tách JSON từ phản hồi LLM với 4 chiến lược fallback "trâu bò".

    LLM đôi khi trả về JSON bọc trong nhiều dạng khác nhau:
        Dạng 1 (lý tưởng): {"intents": [...], ...}
        Dạng 2: ```json\\n{...}\\n```
        Dạng 3: ```\\n{...}\\n```
        Dạng 4: Có text phía trước/sau: "Here is the JSON:\\n{...}\\nDone."
        Dạng 5 (tệ nhất): JSON lồng nhau, escaped quotes, ...

    Chiến lược (thứ tự ưu tiên):
        [S1] Parse trực tiếp (happy path — Gemini JSON mode thường thành công)
        [S2] Regex: trích JSON trong block ```json ... ```
        [S3] Regex: trích JSON trong block ``` ... ```
        [S4] Regex: tìm object JSON đầu tiên { ... } trong toàn bộ text
        [S5] Trả về dict rỗng + log warning (không raise exception)

    Args:
        text:    Chuỗi phản hồi từ Gemini.
        context: Label để phân biệt log (ví dụ: "classify_intent").

    Returns:
        dict đã parse, hoặc {} nếu tất cả chiến lược thất bại.
    """
    if not text or not text.strip():
        logger.warning("[JSON/%s] Phản hồi rỗng từ LLM.", context)
        return {}

    cleaned = text.strip()

    # --- [S1] Parse trực tiếp (Gemini JSON mode thường cho kết quả này) ---
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            logger.debug("[JSON/%s] S1 thành công: parse trực tiếp.", context)
            return result
    except json.JSONDecodeError:
        pass

    # --- [S2] Trích từ ```json ... ``` block ---
    # Pattern: optional whitespace, ```json, optional newline, capture {...}, optional newline, ```
    json_block_pattern = re.compile(
        r"```json\s*\n?([\s\S]*?)\n?\s*```",
        re.IGNORECASE,
    )
    match = json_block_pattern.search(cleaned)
    if match:
        candidate = match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                logger.debug("[JSON/%s] S2 thành công: ```json block.", context)
                return result
        except json.JSONDecodeError as e:
            logger.debug("[JSON/%s] S2 parse fail: %s", context, e)

    # --- [S3] Trích từ ``` ... ``` block (không có chỉ định ngôn ngữ) ---
    generic_block_pattern = re.compile(
        r"```\s*\n?([\s\S]*?)\n?\s*```",
    )
    match = generic_block_pattern.search(cleaned)
    if match:
        candidate = match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                logger.debug("[JSON/%s] S3 thành công: ``` generic block.", context)
                return result
        except json.JSONDecodeError as e:
            logger.debug("[JSON/%s] S3 parse fail: %s", context, e)

    # --- [S4] Tìm JSON object đầu tiên trong toàn bộ text ---
    # Regex greedy: tìm { đến } cuối cùng của chuỗi (xử lý JSON lồng nhau)
    # re.DOTALL để . khớp với cả newline
    brace_pattern = re.compile(r"\{[\s\S]*\}", re.DOTALL)
    match = brace_pattern.search(cleaned)
    if match:
        candidate = match.group(0).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                logger.debug("[JSON/%s] S4 thành công: brace extraction.", context)
                return result
        except json.JSONDecodeError:
            # S4b: thử brace greedy từ phải sang (lấy phần { ... } dài nhất)
            # Hữu ích khi có text lẫn lộn giữa 2 JSON objects
            all_matches = brace_pattern.findall(cleaned)
            for candidate in sorted(all_matches, key=len, reverse=True):
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        logger.debug(
                            "[JSON/%s] S4b thành công: longest brace match.", context
                        )
                        return result
                except json.JSONDecodeError:
                    continue

    # --- [S5] Tất cả chiến lược thất bại ---
    logger.warning(
        "[JSON/%s] TẤT CẢ chiến lược parse thất bại. "
        "Raw response (100 ký tự đầu): %r",
        context,
        cleaned[:100],
    )
    return {}


def _normalize_intents(raw_intents: Any) -> list[str]:
    """
    Validate và chuẩn hóa danh sách intent từ Gemini output.

    - Đảm bảo kiểu list[str]
    - Lọc bỏ intent không hợp lệ
    - Fallback về ["other"] nếu rỗng hoàn toàn
    """
    if not isinstance(raw_intents, list):
        logger.warning(
            "[Normalize] intents không phải list: %r → fallback ['get_major_info']", raw_intents
        )
        return ["get_major_info"]

    valid = [i for i in raw_intents if isinstance(i, str) and i in VALID_INTENTS]

    if not valid:
        logger.warning(
            "[Normalize] Không có intent hợp lệ trong %r → fallback ['get_major_info']",
            raw_intents,
        )
        return ["get_major_info"]

    return valid


def _normalize_queries(raw_queries: Any, fallback: str = "") -> list[str]:
    """
    Validate và chuẩn hóa danh sách search queries.

    - Đảm bảo kiểu list[str]
    - Lọc bỏ chuỗi rỗng
    - Fallback về [câu hỏi gốc] nếu rỗng
    """
    if not isinstance(raw_queries, list):
        logger.warning(
            "[Normalize] queries không phải list: %r → fallback câu hỏi gốc",
            raw_queries,
        )
        return [fallback] if fallback else []

    valid = [q.strip() for q in raw_queries if isinstance(q, str) and q.strip()]

    if not valid:
        logger.warning(
            "[Normalize] Queries rỗng sau khi lọc → fallback câu hỏi gốc."
        )
        return [fallback] if fallback else []

    return valid[:3]  # Giới hạn tối đa 3 queries để kiểm soát chi phí API


def _normalize_filters(raw_filters: Any) -> dict[str, Any]:
    """
    Validate và chuẩn hóa dynamic_filters từ Gemini output.

    - Đảm bảo kiểu dict
    - Cast year sang int (hoặc None)
    - Validate doc_type trong VALID_DOC_TYPES
    """
    if not isinstance(raw_filters, dict):
        logger.warning(
            "[Normalize] filters không phải dict: %r → trả về {}", raw_filters
        )
        return {"year": None, "doc_type": None}

    # --- Xử lý year ---
    raw_year = raw_filters.get("year")
    year: int | None = None
    if raw_year is not None:
        try:
            year = int(raw_year)
            if not (2000 <= year <= 2100):
                logger.warning("[Normalize] year=%d nằm ngoài range [2000,2100] → None", year)
                year = None
        except (ValueError, TypeError):
            logger.warning("[Normalize] year=%r không thể cast sang int → None", raw_year)
            year = None

    # --- Xử lý doc_type ---
    raw_doc_type = raw_filters.get("doc_type")
    doc_type: str | None = None
    if isinstance(raw_doc_type, str) and raw_doc_type.strip() in VALID_DOC_TYPES:
        doc_type = raw_doc_type.strip()
    elif raw_doc_type is not None:
        logger.warning(
            "[Normalize] doc_type=%r không hợp lệ → None. "
            "Hợp lệ: %s", raw_doc_type, VALID_DOC_TYPES,
        )

    result = {"year": year, "doc_type": doc_type}
    logger.debug("[Normalize] Filters sau chuẩn hóa: %s", result)
    return result


def _format_context(results: list[dict]) -> str:
    """
    Format danh sách search results thành chuỗi context cho Gemini.

    Mỗi chunk được bọc với metadata nguồn tài liệu để Gemini
    có thể trích dẫn chính xác trong câu trả lời.
    """
    if not results:
        return ""

    parts: list[str] = []
    for i, r in enumerate(results, start=1):
        meta         = r.get("metadata", {})
        source_file  = meta.get("source_file", "Tài liệu ĐH Vinh")
        page         = meta.get("page", "?")
        doc_type     = meta.get("doc_type", "")
        year         = meta.get("year", "")
        score        = r.get("score", 0)
        content      = r.get("content", "").strip()

        # Header tham chiếu nguồn giúp Gemini trích dẫn đúng
        header = (
            f"[Nguồn {i}: {source_file}"
            + (f", năm {year}" if year else "")
            + (f", loại: {doc_type}" if doc_type else "")
            + f", trang {page}, độ liên quan: {score:.2f}]"
        )
        parts.append(f"{header}\n{content}")

    return "\n\n---\n\n".join(parts)


def _static_fallback_message() -> str:
    """Thông báo fallback chuẩn khi không tìm thấy thông tin tuyển sinh."""
    return (
        "Hiện tại hệ thống dữ liệu tuyển sinh của Trường Đại học Vinh chưa tìm thấy "
        "thông tin chính xác để giải đáp câu hỏi này. 🙏\n\n"
        "**Để được hỗ trợ trực tiếp, thí sinh vui lòng liên hệ:**\n"
        "- 🏫 **Hội đồng Tuyển sinh Trường Đại học Vinh**\n"
        "- 📍 Địa chỉ: Số 182 Lê Duẩn, TP. Vinh, Nghệ An\n"
        "- 🌐 Website: [tuyensinh.vinhuni.edu.vn](https://tuyensinh.vinhuni.edu.vn)\n\n"
        "*Chúc thí sinh thành công trong kỳ thi tuyển sinh!*"
    )
