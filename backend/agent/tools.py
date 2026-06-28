"""
agent/tools.py
==============
Công cụ lõi của Agent — Cổng tìm kiếm duy nhất và tính toán điểm chuẩn.

Triết lý thiết kế:
- `search_admission_info()` là điểm kiểm soát DUY NHẤT cho toàn bộ
  luồng tìm kiếm của hệ thống. Mọi thao tác đều đi qua đây —
  giúp tập trung logging, monitoring và dễ mock khi test.
- Logging chi tiết ở mọi bước để debug production:
    [1] Log filter đang được apply (field, value, type)
    [2] Log số kết quả trả về và score range
    [3] Log warning nếu embed thất bại
- Tách biệt hàm embed và search để lỗi ở từng bước được xử lý riêng.
"""

import logging
from typing import Any

from core.embedder import embed
from core.vectordb import search as qdrant_search

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hằng số cấu hình Tool
# ---------------------------------------------------------------------------

DEFAULT_TOP_K: int = 5
"""Số lượng chunk trả về mỗi lần search (trước deduplicate)."""

SCORE_THRESHOLD: float = 0.30
"""
Ngưỡng cosine similarity tối thiểu.
Kết quả dưới ngưỡng này bị loại ngay tại Qdrant (không được trả về).
Giá trị 0.30 là thực nghiệm tốt với bge-m3 cho tiếng Việt.
"""

# Danh sách filter key hợp lệ để log cảnh báo khi nhận key lạ
_KNOWN_FILTER_KEYS: frozenset[str] = frozenset({"year", "doc_type"})


# ---------------------------------------------------------------------------
# Tool 1: Tìm kiếm thông tin tuyển sinh
# ---------------------------------------------------------------------------

def search_admission_info(
    query: str,
    filters: dict[str, Any] | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    Tìm kiếm thông tin tuyển sinh trong Vector Database.

    Đây là cổng tìm kiếm DUY NHẤT của hệ thống — mọi node trong LangGraph
    phải gọi qua hàm này thay vì gọi trực tiếp core/vectordb.py.
    Điều này đảm bảo logging và behavior nhất quán toàn hệ thống.

    Luồng xử lý nội bộ:
        query (str)
            │
            ├─[1] Validate & log query
            │
            ├─[2] Embed query → vector[1024] via BAAI/bge-m3
            │       └─ RuntimeError → trả về [] ngay
            │
            ├─[3] Log filter parameters chi tiết (field, value, type)
            │       └─ Cảnh báo nếu có filter key không chuẩn
            │
            └─[4] Qdrant hybrid search (vector + hard filter)
                    └─ Exception → trả về []

    Args:
        query:   Cụm từ tìm kiếm đã được tối ưu hóa bởi classify node.
                 Không được rỗng.
        filters: Dict bộ lọc metadata (từ dynamic_filters trong state).
                 Các key hợp lệ: "year" (int), "doc_type" (str).
                 Giá trị None cho từng key → không áp dụng filter field đó.
                 None hoàn toàn → search không filter (toàn collection).
        top_k:   Số kết quả tối đa muốn lấy (trước deduplicate ở node search).

    Returns:
        List[dict] các chunk tìm thấy, đã sắp xếp theo score giảm dần:
        [
            {
                "content":  "Ngành Kỹ thuật phần mềm, mã ngành 7480103...",
                "score":    0.8912,
                "metadata": {
                    "source_file": "tuyen_sinh_2026.pdf",
                    "year":        2026,
                    "doc_type":    "diem_chuan",
                    "faculty":     "Khoa CNTT",
                    "page":        4
                }
            },
            ...
        ]
        Trả về [] nếu không tìm thấy kết quả hoặc có lỗi.
    """
    # --- [1] Validate query ---
    if not query or not query.strip():
        logger.warning("[Tools/Search] Query rỗng — bỏ qua search.")
        return []

    clean_query = query.strip()
    active_filters = filters or {}

    logger.info(
        "[Tools/Search] ═══ BẮT ĐẦU TÌM KIẾM ═══\n"
        "  Query  : %r\n"
        "  Top-K  : %d\n"
        "  Threshold: %.2f",
        clean_query,
        top_k,
        SCORE_THRESHOLD,
    )

    # --- [2] Log filter chi tiết để debug ---
    _log_filters(active_filters)

    # --- [3] Embed query → vector ---
    try:
        query_vector = embed(clean_query)
        logger.debug(
            "[Tools/Search] Embed thành công | vector dim=%d | norm≈1.0",
            len(query_vector),
        )
    except (RuntimeError, ValueError) as embed_err:
        logger.error(
            "[Tools/Search] Embed thất bại cho query %r: %s — trả về []",
            clean_query,
            str(embed_err),
            exc_info=True,
        )
        return []

    # --- [4] Qdrant search ---
    try:
        results = qdrant_search(
            query_vector=query_vector,
            filters=active_filters,
            top_k=top_k,
            score_threshold=SCORE_THRESHOLD,
        )

        # Log kết quả tổng quan
        if results:
            scores = [r["score"] for r in results]
            logger.info(
                "[Tools/Search] ═══ KẾT QUẢ ═══\n"
                "  Tìm thấy : %d chunks\n"
                "  Score cao nhất : %.4f\n"
                "  Score thấp nhất: %.4f\n"
                "  Score trung bình: %.4f",
                len(results),
                max(scores),
                min(scores),
                sum(scores) / len(scores),
            )
            # Log snippet ngắn của top-1 để xác nhận nội dung
            top_content = results[0]["content"][:120].replace("\n", " ")
            logger.debug(
                "[Tools/Search] Top-1 preview: %r...", top_content
            )
        else:
            logger.info(
                "[Tools/Search] Không tìm thấy kết quả nào (query=%r, filter=%s).",
                clean_query,
                _format_filters_for_log(active_filters),
            )

        return results

    except Exception as search_err:
        logger.error(
            "[Tools/Search] Lỗi khi search Qdrant: %s", str(search_err), exc_info=True
        )
        return []


# ---------------------------------------------------------------------------
# Tool 2: Tính toán điều kiện đủ điểm
# ---------------------------------------------------------------------------

def calculate_eligibility(
    user_score: float,
    threshold: float,
    major_name: str = "",
    year: int | None = None,
) -> str:
    """
    Tính toán và trả về kết luận tư vấn điều kiện trúng tuyển.

    Hàm này là pure function (không có side effect) — dễ test và tái sử dụng.
    Kết quả trả về dưới dạng câu văn tư vấn hoàn chỉnh để LLM có thể
    nhúng trực tiếp vào phản hồi mà không cần xử lý thêm.

    Args:
        user_score:   Tổng điểm xét tuyển của thí sinh (theo thang điểm 30).
                      Ví dụ: 24.5
        threshold:    Điểm chuẩn ngành từ Qdrant (lấy từ search_results).
                      Ví dụ: 25.0
        major_name:   Tên ngành để cá nhân hóa câu trả lời. Tùy chọn.
                      Ví dụ: "Kỹ thuật phần mềm"
        year:         Năm tuyển sinh để ngữ cảnh hóa. Tùy chọn.
                      Ví dụ: 2026

    Returns:
        Chuỗi kết luận tư vấn đầy đủ. Ví dụ:
        - ĐỦ: "Thí sinh CÓ ĐỦ điều kiện nộp hồ sơ xét tuyển ngành Kỹ thuật phần
               mềm (điểm xét tuyển: 24.50 ≥ điểm chuẩn năm 2026: 24.00)."
        - THIẾU: "Thí sinh CHƯA ĐỦ điều kiện xét tuyển ngành Kỹ thuật phần mềm
                  (điểm xét tuyển: 24.50 < điểm chuẩn năm 2026: 25.00,
                  thiếu 0.50 điểm)."
        - LỖI INPUT: Chuỗi mô tả lỗi validate.

    Raises:
        Không raise — mọi lỗi được trả về dưới dạng chuỗi thông báo.
    """
    # --- Validate input ---
    if not isinstance(user_score, (int, float)):
        logger.error(
            "[Tools/Eligibility] user_score không hợp lệ: %r (type=%s)",
            user_score, type(user_score).__name__,
        )
        return "Không thể tính toán: điểm xét tuyển không hợp lệ."

    if not isinstance(threshold, (int, float)):
        logger.error(
            "[Tools/Eligibility] threshold không hợp lệ: %r (type=%s)",
            threshold, type(threshold).__name__,
        )
        return "Không thể tính toán: điểm chuẩn tham chiếu không hợp lệ."

    if not (0 <= user_score <= 30):
        logger.warning(
            "[Tools/Eligibility] user_score=%.2f nằm ngoài thang điểm [0, 30].",
            user_score,
        )
        return (
            f"Điểm xét tuyển {user_score:.2f} nằm ngoài thang điểm hợp lệ (0–30). "
            "Vui lòng kiểm tra lại điểm số."
        )

    if not (10 <= threshold <= 30):
        logger.warning(
            "[Tools/Eligibility] threshold=%.2f nằm ngoài ngưỡng hợp lý [10, 30].",
            threshold,
        )
        # Vẫn tính nhưng cảnh báo — không block người dùng

    # --- Xây dựng phần ngữ cảnh cho câu trả lời ---
    major_part = f" ngành **{major_name}**" if major_name else ""
    year_part = f" năm {year}" if year else ""

    logger.info(
        "[Tools/Eligibility] Tính eligibility | major=%r | "
        "user=%.2f | threshold=%.2f | year=%s",
        major_name or "Không rõ",
        user_score,
        threshold,
        str(year) if year else "Không rõ",
    )

    # --- Tính kết quả ---
    diff = round(user_score - threshold, 2)

    if diff >= 0:
        result = (
            f"✅ Thí sinh **CÓ ĐỦ** điều kiện nộp hồ sơ xét tuyển{major_part} "
            f"(điểm xét tuyển: **{user_score:.2f}** ≥ điểm chuẩn{year_part}: "
            f"**{threshold:.2f}**, vượt **{diff:.2f} điểm**)."
        )
        logger.info(
            "[Tools/Eligibility] → ĐỦ ĐIỀU KIỆN | chênh lệch=+%.2f", diff
        )
    else:
        shortage = abs(diff)
        result = (
            f"❌ Thí sinh **CHƯA ĐỦ** điều kiện xét tuyển{major_part} "
            f"(điểm xét tuyển: **{user_score:.2f}** < điểm chuẩn{year_part}: "
            f"**{threshold:.2f}**, còn thiếu **{shortage:.2f} điểm**)."
        )
        logger.info(
            "[Tools/Eligibility] → CHƯA ĐỦ ĐIỀU KIỆN | thiếu=%.2f", shortage
        )

    return result


# ---------------------------------------------------------------------------
# Private Logging Helpers
# ---------------------------------------------------------------------------

def _log_filters(filters: dict[str, Any]) -> None:
    """
    Log chi tiết từng field của filter đang được áp dụng.
    Giúp debug nhanh khi search không trả về kết quả đúng.
    """
    if not filters:
        logger.info("[Tools/Search] Filters: KHÔNG có filter — search toàn bộ collection.")
        return

    # Kiểm tra field lạ (không nằm trong _KNOWN_FILTER_KEYS)
    unknown_keys = set(filters.keys()) - _KNOWN_FILTER_KEYS
    if unknown_keys:
        logger.warning(
            "[Tools/Search] Filter keys không chuẩn sẽ bị bỏ qua bởi Qdrant: %s",
            unknown_keys,
        )

    # Log từng filter field
    active_count = 0
    logger.info("[Tools/Search] Filters đang được áp dụng:")
    for key in sorted(filters.keys()):
        value = filters[key]
        if value is None:
            logger.info(
                "[Tools/Search]   ├─ %-12s = None  → BỎ QUA (không filter field này)",
                key,
            )
        else:
            value_type = type(value).__name__
            logger.info(
                "[Tools/Search]   ├─ %-12s = %-20r  [type: %s]  → ÁP DỤNG",
                key, value, value_type,
            )
            active_count += 1

    if active_count == 0:
        logger.info(
            "[Tools/Search]   └─ Tất cả giá trị là None → "
            "Không áp dụng hard filter nào."
        )
    else:
        logger.info(
            "[Tools/Search]   └─ Tổng: %d/%d filter fields được kích hoạt.",
            active_count, len(filters),
        )


def _format_filters_for_log(filters: dict[str, Any]) -> str:
    """Tóm tắt filters thành chuỗi ngắn cho single-line log."""
    if not filters:
        return "none"
    parts = [
        f"{k}={v!r}" for k, v in sorted(filters.items()) if v is not None
    ]
    return "{" + ", ".join(parts) + "}" if parts else "none"
