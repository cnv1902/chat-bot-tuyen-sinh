"""
api/routers/chat.py
===================
Endpoint chính: POST /api/chat — Cổng giao tiếp của LangGraph Agent.

Luồng xử lý một request:
    [1] Validate request (Pydantic v2 tự động)
    [2] Lấy lịch sử hội thoại từ Redis (graceful: [] nếu Redis down)
    [3] Khởi tạo AdmissionState đầy đủ qua make_initial_state()
    [4] Gọi admission_graph.invoke() — chạy toàn bộ LangGraph pipeline
    [5] Cập nhật lịch sử: thêm lượt mới, giữ 20 lượt gần nhất
    [6] Lưu lịch sử mới vào Redis (graceful: bỏ qua nếu Redis down)
    [7] Deduplicate sources theo thứ tự score (dict.fromkeys)
    [8] Trả ChatResponse về client

Xử lý lỗi:
    - LangGraph raise → HTTPException 500 với message thân thiện
    - Không expose internal traceback ra response (security)
    - Log full traceback nội bộ để debug
"""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from agent.graph import admission_graph
from agent.state import make_initial_state
from api.schemas import ChatRequest, ChatResponse
from core.session import get_history, save_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])


# ---------------------------------------------------------------------------
# Helper: Deduplicate sources giữ thứ tự (dict.fromkeys trick)
# ---------------------------------------------------------------------------

def _deduplicate_sources(search_results: list[dict]) -> list[str]:
    """
    Trích xuất danh sách tên file nguồn từ search_results, không trùng lặp,
    GIỮ NGUYÊN THỨ TỰ xuất hiện (file score cao nhất → trước).

    Tại sao KHÔNG dùng set():
        set() → mất thứ tự, file quan trọng nhất (score cao) có thể
                bị đẩy xuống cuối danh sách một cách ngẫu nhiên.

    Tại sao dùng dict.fromkeys():
        dict.fromkeys(iterable) giữ nguyên thứ tự xuất hiện đầu tiên
        của mỗi key (Python 3.7+ đảm bảo insertion-ordered dict).
        Các phần tử trùng lặp tiếp theo bị bỏ qua tự động.

    Ví dụ:
        results = [
            {"metadata": {"source_file": "DeAn2026.pdf"}},   # score 0.91
            {"metadata": {"source_file": "QuyCheTD.pdf"}},   # score 0.75
            {"metadata": {"source_file": "DeAn2026.pdf"}},   # score 0.60 (dup)
        ]
        → ["DeAn2026.pdf", "QuyCheTD.pdf"]   ✅ thứ tự giữ nguyên, không dup

    Args:
        search_results: Danh sách dict từ state["search_results"].

    Returns:
        Danh sách tên file không trùng, theo thứ tự score giảm dần.
    """
    raw_sources = [
        r.get("metadata", {}).get("source_file", "")
        for r in search_results
        if r.get("metadata", {}).get("source_file", "").strip()
    ]
    # dict.fromkeys: key đầu tiên được giữ lại, key trùng bị bỏ qua
    return list(dict.fromkeys(raw_sources))


# ---------------------------------------------------------------------------
# Endpoint: POST /api/chat
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Gửi câu hỏi tuyển sinh và nhận câu trả lời từ chatbot",
    description=(
        "Endpoint chính của Chatbot Tuyển sinh ĐH Vinh. "
        "Nhận câu hỏi của thí sinh, chạy Agentic RAG pipeline (LangGraph + Gemini + Qdrant) "
        "và trả về câu trả lời kèm nguồn tài liệu tham chiếu."
    ),
    responses={
        200: {"description": "Câu trả lời thành công"},
        422: {"description": "Dữ liệu đầu vào không hợp lệ (Pydantic validation)"},
        500: {"description": "Lỗi nội bộ server"},
    },
)
async def chat_endpoint(req: ChatRequest, request: Request) -> ChatResponse:
    """
    Xử lý một lượt hội thoại hoàn chỉnh.

    Args:
        req:     ChatRequest đã được Pydantic v2 validate và sanitize.
        request: FastAPI Request object — dùng để lấy request ID từ header nếu có.

    Returns:
        ChatResponse với câu trả lời và danh sách nguồn tài liệu.
    """
    # Tạo request ID cho tracing (X-Request-ID từ client, hoặc tự sinh)
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    start_time = time.perf_counter()

    logger.info(
        "[Chat/%s] ═══ REQUEST ═══ session=%s | msg=%r",
        request_id,
        req.session_id,
        req.message[:80] + ("..." if len(req.message) > 80 else ""),
    )

    # ── [2] Lấy lịch sử từ Redis ──
    # Graceful: nếu Redis down → trả về [] → chat vẫn hoạt động (không có history)
    chat_history = get_history(req.session_id)
    logger.debug(
        "[Chat/%s] History từ Redis: %d lượt.", request_id, len(chat_history)
    )

    # ── [3] Khởi tạo state ──
    initial_state = make_initial_state(
        session_id=req.session_id,
        user_message=req.message,
        history=chat_history,
    )

    # ── [4] Chạy LangGraph pipeline ──
    # admission_graph.invoke() là sync và các LangGraph node bên trong
    # dùng asyncio.run() để gọi async LLM providers.
    # Phải chạy trong thread riêng (to_thread) để tránh lỗi:
    # "asyncio.run() cannot be called from a running event loop"
    try:
        from agent.nodes import set_main_loop as _nodes_set_loop
        _nodes_set_loop(asyncio.get_running_loop())

        logger.debug("[Chat/%s] Khởi chạy admission_graph.invoke() trong thread pool...", request_id)
        result_state = await asyncio.to_thread(admission_graph.invoke, initial_state)

    except Exception as graph_err:
        elapsed = round((time.perf_counter() - start_time) * 1000)
        logger.error(
            "[Chat/%s] LangGraph pipeline THẤT BẠI sau %dms: %s",
            request_id, elapsed, str(graph_err),
            exc_info=True,   # Log full traceback để debug nội bộ
        )
        # KHÔNG expose traceback ra ngoài — chỉ trả lỗi generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Hệ thống tạm thời gặp sự cố kỹ thuật. "
                "Vui lòng thử lại sau hoặc liên hệ Hotline tuyển sinh ĐH Vinh."
            ),
        )

    # ── [5] Cập nhật lịch sử ──
    bot_answer = result_state.get("final_answer", "")

    # ── Strip thinking trace ──
    # Qwen3 và một số reasoning model xuất <think>...</think> trước câu trả lời thực sự.
    # Loại bỏ toàn bộ khối thinking trước khi gửi về frontend và lưu Redis.
    import re as _re
    bot_answer = _re.sub(r'<think>.*?</think>', '', bot_answer, flags=_re.DOTALL).strip()

    # Validate output — LangGraph không nên trả về final_answer rỗng
    if not bot_answer.strip():
        logger.warning(
            "[Chat/%s] final_answer rỗng từ LangGraph — dùng fallback message.",
            request_id,
        )
        bot_answer = (
            "Xin lỗi, hệ thống tạm thời không thể xử lý câu hỏi này. "
            "Vui lòng thử lại hoặc liên hệ trực tiếp Hội đồng Tuyển sinh ĐH Vinh."
        )

    # Thêm lượt hội thoại mới vào history
    updated_history = chat_history + [
        {"role": "user",      "content": req.message},
        {"role": "assistant", "content": bot_answer},
    ]

    # Giữ tối đa 20 messages (10 lượt hội thoại) để không vượt context window
    trimmed_history = updated_history[-20:]

    # ── [6] Lưu lịch sử vào Redis ──
    # Graceful: nếu Redis down → log warning, không crash API
    save_ok = save_history(req.session_id, trimmed_history)
    if not save_ok:
        logger.warning(
            "[Chat/%s] Không lưu được history vào Redis (session=%s). "
            "Chat vẫn hoạt động nhưng lịch sử lượt này bị mất.",
            request_id, req.session_id,
        )

    # ── [7] Trích xuất và deduplicate sources ──
    search_results = result_state.get("search_results", [])
    sources = _deduplicate_sources(search_results)

    # ── Logging tổng kết ──
    elapsed_ms = round((time.perf_counter() - start_time) * 1000)
    logger.info(
        "[Chat/%s] ═══ HOÀN THÀNH ═══ %dms | "
        "intents=%s | results=%d | sources=%d | answer=%d ký tự",
        request_id,
        elapsed_ms,
        result_state.get("intents", []),
        len(search_results),
        len(sources),
        len(bot_answer),
    )

    # ── [8] Trả response ──
    return ChatResponse(
        session_id=req.session_id,
        answer=bot_answer,
        sources=sources,
    )
