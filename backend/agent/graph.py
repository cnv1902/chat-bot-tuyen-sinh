"""
agent/graph.py
==============
Đóng gói và Compile LangGraph StateGraph — Admission RAG Workflow.

Sơ đồ đồ thị đầy đủ:
═══════════════════════════════════════════════════════════════
  START
    │
    ▼
 [classify]          ← Node 1: Phân loại intent + trích filter
    │
    │ (edge cố định)
    ▼
 [search]            ← Node 2: Vector search Qdrant
    │
    │ (edge cố định)
    ▼
 [check]             ← Node 3: Tăng iteration counter
    │
    │ (conditional edge — route_after_check)
    ├──── "trigger_generation" ──► [generate] ──► END
    │                                ↑
    │                          Node 4: Sinh câu trả lời
    │
    ├──── "retry_search_loop" ──► [search]   (quay lại Node 2)
    │                              (tối đa MAX_SEARCH_ITERATIONS lần)
    │
    └──── "trigger_fallback"  ──► [fallback] ──► END
                                   ↑
                             Node 5: Câu trả lời dự phòng
═══════════════════════════════════════════════════════════════

Export:
    admission_graph  — CompiledGraph sẵn sàng gọi .invoke() hoặc .astream()
    build_graph()    — Factory function để test / tạo lại graph khi cần
"""

import logging

from langgraph.graph import END, StateGraph

from .state import AdmissionState
from .nodes import (
    classify_intent,
    search_knowledge,
    check_context,
    route_after_check,   # Conditional Edge function — KHÔNG phải Node
    generate_answer,
    fallback_answer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tên Node — Định nghĩa tập trung để tránh magic string phân tán
# ---------------------------------------------------------------------------
# Đặt thành hằng số để:
#   1. Refactor tên node không bao giờ bỏ sót chỗ nào
#   2. IDE có thể detect typo ngay khi gõ
#   3. Dễ tìm kiếm reference trong codebase lớn

NODE_CLASSIFY  = "classify"
NODE_SEARCH    = "search"
NODE_CHECK     = "check"
NODE_GENERATE  = "generate"
NODE_FALLBACK  = "fallback"

# Tên route keys — phải khớp chính xác với giá trị trả về của route_after_check()
ROUTE_GENERATE = "trigger_generation"
ROUTE_RETRY    = "retry_search_loop"
ROUTE_FALLBACK = "trigger_fallback"


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Xây dựng và compile LangGraph StateGraph cho Admission RAG workflow.

    Được tách thành hàm riêng (thay vì code ở module level) để:
    - Dễ unit test: gọi build_graph() trong fixture, mock node functions
    - Dễ recreate khi cần: không bị ràng buộc vào module import order
    - Rõ ràng hơn về lifecycle: compile xảy ra khi nào

    Returns:
        CompiledGraph — Đã qua .compile(), sẵn sàng gọi .invoke()/.astream()

    Raises:
        ValueError: Nếu graph configuration không hợp lệ (thiếu node, vòng lặp vô hạn...)
                    LangGraph tự phát hiện và raise khi compile.
    """
    logger.info("[Graph] Bắt đầu khởi tạo Admission RAG StateGraph...")

    # ── Khởi tạo StateGraph với AdmissionState ──
    # LangGraph dùng schema TypedDict để validate state shape tại runtime
    workflow = StateGraph(AdmissionState)

    # ── Đăng ký các Nodes ──
    # Thứ tự đăng ký không quan trọng — chỉ tên và function mapping mới quan trọng
    workflow.add_node(NODE_CLASSIFY, classify_intent)
    workflow.add_node(NODE_SEARCH,   search_knowledge)
    workflow.add_node(NODE_CHECK,    check_context)
    workflow.add_node(NODE_GENERATE, generate_answer)
    workflow.add_node(NODE_FALLBACK, fallback_answer)

    logger.debug(
        "[Graph] Đã đăng ký %d nodes: %s",
        5,
        [NODE_CLASSIFY, NODE_SEARCH, NODE_CHECK, NODE_GENERATE, NODE_FALLBACK],
    )

    # ── Thiết lập Entry Point ──
    # Node đầu tiên được thực thi khi graph nhận input
    workflow.set_entry_point(NODE_CLASSIFY)

    # ── Edges Cố Định (Deterministic Edges) ──
    # classify → search: Luôn chạy search sau khi đã có intents + queries + filters
    workflow.add_edge(NODE_CLASSIFY, NODE_SEARCH)

    # search → check: Luôn kiểm tra quality context sau mỗi lần search
    workflow.add_edge(NODE_SEARCH, NODE_CHECK)

    # generate → END: Sau khi sinh câu trả lời, workflow kết thúc
    workflow.add_edge(NODE_GENERATE, END)

    # fallback → END: Sau khi trả lời dự phòng, workflow kết thúc
    workflow.add_edge(NODE_FALLBACK, END)

    # ── Conditional Edge: check → (generate | search | fallback) ──
    #
    # Đây là điểm định tuyến TRUNG TÂM của toàn bộ Agentic RAG:
    #
    #   route_after_check(state) → str
    #       │
    #       ├── "trigger_generation" → NODE_GENERATE
    #       │   Khi: context đủ tốt (≥ MIN_CONTEXT_LENGTH ký tự)
    #       │        VÀ intent không phải "other"
    #       │
    #       ├── "retry_search_loop" → NODE_SEARCH
    #       │   Khi: context chưa đủ (< MIN_CONTEXT_LENGTH)
    #       │        VÀ còn lượt retry (iterations < MAX_SEARCH_ITERATIONS)
    #       │   ⚠️  Tạo vòng lặp: search → check → search → check → ...
    #       │       An toàn vì MAX_SEARCH_ITERATIONS = 3 (giới hạn cứng)
    #       │
    #       └── "trigger_fallback" → NODE_FALLBACK
    #           Khi: intent là "other"
    #                HOẶC đã hết lượt retry mà vẫn thiếu context
    #
    # QUAN TRỌNG: Mapping dict phải COVER đầy đủ tất cả giá trị
    # có thể trả về bởi route_after_check() — nếu thiếu key,
    # LangGraph sẽ raise InvalidUpdateError tại runtime.
    #
    workflow.add_conditional_edges(
        source=NODE_CHECK,
        path=route_after_check,
        path_map={
            # route key          → node đích
            ROUTE_GENERATE: NODE_GENERATE,  # "trigger_generation" → [generate]
            ROUTE_RETRY:    NODE_SEARCH,    # "retry_search_loop"  → [search]
            ROUTE_FALLBACK: NODE_FALLBACK,  # "trigger_fallback"   → [fallback]
        },
    )

    logger.debug(
        "[Graph] Conditional edges từ '%s': %s",
        NODE_CHECK,
        {ROUTE_GENERATE: NODE_GENERATE, ROUTE_RETRY: NODE_SEARCH, ROUTE_FALLBACK: NODE_FALLBACK},
    )

    # ── Compile ──
    # Bước này validate toàn bộ graph:
    # - Kiểm tra không có node "mồ côi" (không có edge đến/đi)
    # - Kiểm tra path_map cover đủ outputs của condition function
    # - Build execution plan tối ưu
    compiled = workflow.compile()

    logger.info(
        "[Graph] StateGraph compile thành công.\n"
        "  Entry   : %s\n"
        "  Nodes   : %s → %s → %s → (%s | %s)\n"
        "  Max Loop: %d lần retry trước fallback",
        NODE_CLASSIFY,
        NODE_CLASSIFY, NODE_SEARCH, NODE_CHECK,
        NODE_GENERATE, NODE_FALLBACK,
        3,  # MAX_SEARCH_ITERATIONS — không import để tránh circular dependency
    )

    return compiled


# ---------------------------------------------------------------------------
# Module-level Singleton — Import và dùng ngay trong api/routers/chat.py
# ---------------------------------------------------------------------------

# Compile một lần duy nhất khi module được import lần đầu.
# Các lần import sau đều nhận cùng một compiled graph object.
#
# ⚠️  LƯU Ý PRODUCTION: Nếu cần hot-reload graph (thay đổi prompt không restart),
# hãy dùng build_graph() trong một background task và swap reference bằng Lock.
# Hiện tại thiết kế này đủ tốt cho single-instance deployment.
try:
    admission_graph = build_graph()
    logger.info("[Graph] admission_graph đã sẵn sàng phục vụ requests.")
except Exception as build_err:
    logger.critical(
        "[Graph] KHÔNG THỂ compile admission_graph: %s\n"
        "API sẽ KHÔNG hoạt động cho đến khi lỗi này được khắc phục.",
        str(build_err),
        exc_info=True,
    )
    # Raise để FastAPI startup event biết và từ chối khởi động
    raise RuntimeError(
        f"LangGraph compilation failed: {build_err}"
    ) from build_err
