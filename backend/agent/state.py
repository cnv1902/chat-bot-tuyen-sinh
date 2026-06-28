"""
agent/state.py
==============
Định nghĩa AdmissionState — Cấu trúc trạng thái trung tâm của LangGraph.

Triết lý thiết kế:
- TypedDict thay vì dataclass/Pydantic để tương thích hoàn toàn
  với LangGraph StateGraph (LangGraph đọc/ghi state qua dict protocol).
- Mỗi field đều có kiểu tường minh + comment giải thích vai trò
  và node nào chịu trách nhiệm cập nhật field đó.
- Không có giá trị mặc định trong TypedDict — caller (api/routers/chat.py)
  phải khởi tạo đầy đủ để tránh lỗi KeyError ngầm trong graph.

Vòng đời của state:
    [Khởi tạo] → classify → search → check → generate/fallback → [Kết quả]
     session_id   intents    results   iter    final_answer
     user_message queries    context
     history      filters
"""

from typing import Any, TypedDict


class AdmissionState(TypedDict):
    """
    Trạng thái đầy đủ của một lượt hội thoại đi qua LangGraph.

    Phân nhóm theo vòng đời:

    [INPUT — Khởi tạo bởi API layer]
        session_id:      UUID định danh phiên chat, dùng làm Redis key.
        user_message:    Câu hỏi thô của thí sinh chưa qua xử lý.
        history:         10-20 lượt hội thoại gần nhất từ Redis
                         (format: [{"role": "user"|"assistant", "content": "..."}])

    [PHÂN LOẠI — Cập nhật bởi node `classify`]
        intents:         Danh sách intent được nhận diện.
                         Giá trị hợp lệ: "check_score", "get_tuition",
                         "get_scholarship", "get_major_info", "other".
        search_queries:  Danh sách cụm từ tìm kiếm được tối ưu hóa ngữ nghĩa
                         từ câu hỏi gốc (Gemini rewrite).
        dynamic_filters: Bộ lọc metadata trích xuất từ ngữ cảnh câu hỏi:
                         {"year": int|None, "doc_type": str|None}

    [TÌM KIẾM — Cập nhật bởi node `search`]
        relaxed_filters: Bộ lọc thật sự được dùng ở lượt search hiện tại sau khi
                         áp dụng chiến lược nới lỏng theo iterations.
        search_results:  Danh sách dict kết quả từ Qdrant, mỗi phần tử:
                         {"content": str, "score": float, "metadata": dict}
        context:         Chuỗi ngữ cảnh đã format, ghép từ top-k search_results,
                         kèm theo thông tin nguồn tài liệu.

    [KIỂM SOÁT VÒNG LẶP — Cập nhật bởi node `check`]
        iterations:      Bộ đếm số lần đã chạy vòng search-check.
                         Giới hạn MAX = 3 lần (route_after_check tự enforce).

    [ĐẦU RA — Cập nhật bởi node `generate` hoặc `fallback`]
        final_answer:    Câu trả lời cuối cùng sẽ được trả về cho người dùng.
                         Trống ("") cho đến khi node generate/fallback chạy.
    """

    # ---------- INPUT ----------
    session_id: str
    """UUID duy nhất định danh phiên chat. Dùng làm key trong Redis."""

    user_message: str
    """Câu hỏi thô của thí sinh, chưa được xử lý hay chuẩn hóa."""

    history: list[dict[str, str]]
    """
    Lịch sử hội thoại gần nhất (tối đa 20 lượt).
    Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """

    # ---------- PHÂN LOẠI ----------
    intents: list[str]
    """
    Danh sách intent được Gemini nhận diện từ câu hỏi.
    Ví dụ: ["check_score", "get_major_info"]
    Luôn chứa ít nhất một phần tử; mặc định là ["other"].
    """

    search_queries: list[str]
    """
    Danh sách cụm từ tìm kiếm semantic được Gemini tối ưu hóa.
    Ví dụ: ["điểm chuẩn Khoa CNTT 2026", "ngành Kỹ thuật phần mềm ĐH Vinh"]
    Dùng làm đầu vào cho search_admission_info() trong node `search`.
    """

    dynamic_filters: dict[str, Any]
    """
    Bộ lọc metadata được trích xuất ngữ cảnh từ câu hỏi.
    Keys có thể có: "year" (int), "doc_type" (str).
    Giá trị None = không áp dụng filter cho field đó.
    Ví dụ: {"year": 2026, "doc_type": "diem_chuan"}
    """

    # ---------- TÌM KIẾM ----------
    relaxed_filters: dict[str, Any]
    """
    Bộ lọc active ở lượt search gần nhất sau khi nới lỏng theo iterations.
    Iteration 0: year + doc_type; iteration 1: chỉ year; iteration >= 2: không filter.
    """

    search_results: list[dict[str, Any]]
    """
    Kết quả thô từ Qdrant sau khi search.
    Mỗi phần tử: {"content": str, "score": float, "metadata": dict}
    Đã được deduplicate và sắp xếp theo score giảm dần trong node `search`.
    """

    context: str
    """
    Chuỗi ngữ cảnh tổng hợp được format từ search_results.
    Đây là nội dung được nhúng vào thẻ <context> trong prompt của node `generate`.
    Rỗng ("") nếu không tìm thấy kết quả liên quan.
    """

    # ---------- KIỂM SOÁT VÒNG LẶP ----------
    iterations: int
    """
    Số lần vòng lặp search → check đã được thực thi.
    Bắt đầu từ 0, tăng 1 sau mỗi lần qua node `check`.
    Khi đạt MAX_SEARCH_ITERATIONS (3), node `check` chuyển sang fallback.
    """

    # ---------- ĐẦU RA ----------
    final_answer: str
    """
    Câu trả lời cuối cùng trả về cho thí sinh.
    Được điền bởi node `generate` (câu trả lời chính thức dựa trên context)
    hoặc node `fallback` (thông báo không tìm thấy thông tin).
    Khởi tạo là "" và KHÔNG ĐƯỢC truy cập trước khi graph chạy xong.
    """


# ---------------------------------------------------------------------------
# Hằng số kiểm soát vòng lặp — Tập trung tại đây để dễ điều chỉnh
# ---------------------------------------------------------------------------

MAX_SEARCH_ITERATIONS: int = 3
"""Số lần tối đa thực hiện vòng lặp retry search trước khi fallback."""

MIN_CONTEXT_LENGTH: int = 40
"""
Độ dài tối thiểu (ký tự) của context để được coi là "có dữ liệu hợp lệ".
Context < 40 ký tự → coi như rỗng → retry hoặc fallback.
"""

VALID_INTENTS: frozenset[str] = frozenset({
    "check_score",
    "get_tuition",
    "get_scholarship",
    "get_major_info",
    "other",
})
"""Tập hợp intent hợp lệ. Intent ngoài danh sách này sẽ bị normalize về 'other'."""

VALID_DOC_TYPES: frozenset[str] = frozenset({
    "diem_chuan",
    "hoc_phi",
    "chi_tieu",
    "quy_che",
    "thong_bao",
})
"""Tập hợp doc_type hợp lệ trong metadata Qdrant."""


def make_initial_state(
    session_id: str,
    user_message: str,
    history: list[dict[str, str]],
) -> AdmissionState:
    """
    Factory function tạo AdmissionState khởi tạo hoàn chỉnh.

    Đảm bảo tất cả field bắt buộc đều có giá trị hợp lệ trước khi
    đưa vào LangGraph — tránh KeyError khi node đầu tiên truy cập state.

    Args:
        session_id:   UUID phiên chat.
        user_message: Câu hỏi của thí sinh.
        history:      Lịch sử hội thoại từ Redis (có thể là []).

    Returns:
        AdmissionState đầy đủ, sẵn sàng truyền vào admission_graph.invoke().

    Example:
        >>> state = make_initial_state("uuid-123", "Điểm chuẩn ngành CNTT?", [])
        >>> result = admission_graph.invoke(state)
    """
    return AdmissionState(
        session_id=session_id,
        user_message=user_message.strip(),
        history=history,
        # Các field dưới đây sẽ được điền bởi từng node
        intents=[],
        search_queries=[],
        dynamic_filters={},
        relaxed_filters={},
        search_results=[],
        context="",
        iterations=0,
        final_answer="",
    )
