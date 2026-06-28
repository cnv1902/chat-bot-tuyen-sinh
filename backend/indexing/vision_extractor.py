"""
indexing/vision_extractor.py
============================
Bước 2: Gửi ảnh JPEG → LLM Vision Provider → JSON có cấu trúc.

Thiết kế mới (Multi-LLM):
- Không hardcode Gemini — gọi get_ocr_provider() để lấy provider từ DB.
- Provider được cấu hình qua Admin UI (/admin/llm-settings).
- Fallback: nếu provider chưa cấu hình → raise ValueError rõ ràng.
- Retry logic được delegate cho từng provider (xem llm/gemini.py).
"""

import asyncio
import json
import logging
import re

from indexing.text_utils import normalize_scope, repair_text_tree

logger = logging.getLogger(__name__)

# Module-level event loop — được set bởi upload.py trước khi gọi asyncio.to_thread.
# Cho phép extract_page_with_gemini() gửi coroutine vào FastAPI event loop
# mà không tạo loop mới (tránh xung đột asyncpg).
_MAIN_LOOP: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Inject FastAPI event loop vào module. Gọi 1 lần từ upload.py."""
    global _MAIN_LOOP
    _MAIN_LOOP = loop

# ---------------------------------------------------------------------------
# System Prompt — Đây là "tâm hồn" của toàn bộ pipeline ETL
# ---------------------------------------------------------------------------

_VISION_PROMPT = """Bạn là chuyên gia số hóa tài liệu tuyển sinh đại học Việt Nam.
Trích xuất CHÍNH XÁC nội dung từ ảnh tài liệu và trả về JSON theo cấu trúc sau.

QUY TẮC BẮT BUỘC:
1. TUYỆT ĐỐI không bịa số liệu — chỉ trích xuất những gì nhìn thấy rõ ràng trên ảnh.
2. Bảng biểu (điểm chuẩn, chỉ tiêu, học phí) → chuyển thành Markdown Table chuẩn xác.
3. Giữ nguyên: mã ngành 7 chữ số, điểm số, học phí, tổ hợp môn xét tuyển.
4. Bỏ qua: số trang, header/footer lặp lại, watermark, dấu mộc.
5. Tự suy luận metadata từ nội dung thực tế của trang.

OUTPUT JSON (chỉ xuất JSON, không thêm bất kỳ ký tự nào khác):
{
  "metadata": {
    "year": <năm tuyển sinh dạng số nguyên, ví dụ 2026. null nếu không thấy>,
    "doc_type": <"diem_chuan"|"hoc_phi"|"chi_tieu"|"quy_che"|"thong_bao"|"khac">,
    "scope": <"all" nếu tài liệu cấp bộ/cấp trường/toàn trường; chỉ dùng tên khoa/viện khi văn bản rõ ràng thuộc riêng khoa/viện đó>
  },
  "content": "<toàn bộ văn bản trích xuất định dạng Markdown>"
}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_page_with_gemini(image_path: str) -> dict:
    """
    Backward-compatible wrapper — gọi extract_page() đồng bộ từ thread worker.

    Khi được gọi từ asyncio.to_thread() (trong FastAPI background task),
    hàm này chạy trong thread pool. Để tránh xung đột event loop với asyncpg,
    sử dụng _MAIN_LOOP (được set từ upload.py trước khi gọi to_thread).
    Nếu không có _MAIN_LOOP, fallback về asyncio.run() cho script độc lập.
    """
    if _MAIN_LOOP is not None and _MAIN_LOOP.is_running():
        # Gửi coroutine vào main event loop của FastAPI, chờ kết quả thread-safe
        future = asyncio.run_coroutine_threadsafe(extract_page(image_path), _MAIN_LOOP)
        return future.result()
    else:
        # Fallback: script CLI, test, hoặc không trong context FastAPI
        return asyncio.run(extract_page(image_path))


async def extract_page(image_path: str) -> dict:
    """
    Trích xuất nội dung một trang tài liệu bằng LLM Vision provider.

    Provider được đọc từ DB slot "ocr" — không hardcode Gemini.
    Thay đổi provider qua Admin UI có hiệu lực ngay lập tức.

    Args:
        image_path: Đường dẫn tới file JPEG cần phân tích.

    Returns:
        dict với 2 key:
            "metadata": {"year": int|None, "doc_type": str, "scope": str}
            "content":  str (Markdown)
        Trả về dict rỗng an toàn nếu provider lỗi.

    Raises:
        ValueError: Khi slot "ocr" chưa được cấu hình trong DB.
    """
    from llm import get_ocr_provider

    try:
        provider = await get_ocr_provider()
    except ValueError as e:
        logger.error("[Vision] Lỗi cấu hình provider: %s", e)
        raise

    raw = await provider.complete_vision(
        image_path=image_path,
        prompt=_VISION_PROMPT,
        max_tokens=4096,
    )

    if not raw:
        logger.warning("[Vision] Provider trả về chuỗi rỗng: %s", image_path)
        return _empty_result()

    parsed = _parse_json_safe(raw, image_path)
    if parsed:
        logger.info(
            "[Vision] OK | file=%s | doc_type=%s | year=%s | content=%d chars",
            image_path,
            parsed.get("metadata", {}).get("doc_type", "?"),
            parsed.get("metadata", {}).get("year", "?"),
            len(parsed.get("content", "")),
        )
        return parsed

    return _empty_result()


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------

def _parse_json_safe(raw: str, source: str = "") -> dict:
    """
    Parse JSON từ response LLM với 4-tầng fallback.
    Tham chiếu: agent/nodes.py::_extract_json_robust()
    """
    # S1: Parse trực tiếp
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "content" in data:
            return _normalize_result(data)
    except json.JSONDecodeError:
        pass

    # S2: ```json ... ```
    m = re.search(r"```json\s*\n?([\s\S]*?)\n?\s*```", raw, re.IGNORECASE)
    if m:
        try:
            data = json.loads(m.group(1).strip())
            if isinstance(data, dict):
                return _normalize_result(data)
        except json.JSONDecodeError:
            pass

    # S3: ``` ... ```
    m = re.search(r"```\s*\n?([\s\S]*?)\n?\s*```", raw)
    if m:
        try:
            data = json.loads(m.group(1).strip())
            if isinstance(data, dict):
                return _normalize_result(data)
        except json.JSONDecodeError:
            pass

    # S4: Tìm { ... } dài nhất
    m = re.search(r"\{[\s\S]*\}", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return _normalize_result(data)
        except json.JSONDecodeError:
            pass

    logger.warning("[Vision] JSON parse hoàn toàn thất bại: %s", source)
    return {}


def _normalize_result(data: dict) -> dict:
    """
    Repair mojibake và chuẩn hóa metadata sang schema scope-only.
    Backward compat: nếu model trả "faculty" thay vì "scope", tự chuyển đổi.
    """
    cleaned  = repair_text_tree(data)
    raw_meta = cleaned.get("metadata", {})
    if not isinstance(raw_meta, dict):
        raw_meta = {}

    scope = raw_meta.get("scope")
    if scope is None:
        scope = raw_meta.get("faculty", "all")

    return {
        "metadata": {
            "year":     raw_meta.get("year"),
            "doc_type": raw_meta.get("doc_type", "khac"),
            "scope":    normalize_scope(scope),
        },
        "content": cleaned.get("content", ""),
    }


def _empty_result() -> dict:
    """Kết quả rỗng an toàn khi LLM không thể xử lý trang."""
    return {
        "metadata": {"year": None, "doc_type": "khac", "scope": "all"},
        "content":  "",
    }
