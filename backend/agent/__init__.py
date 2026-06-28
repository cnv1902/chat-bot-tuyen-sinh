"""
agent/ — LangGraph Agentic RAG cho Chatbot Tuyển sinh ĐH Vinh.

Thứ tự dependency nội bộ (bottom-up):
    state.py   → Định nghĩa AdmissionState (TypedDict)
    tools.py   → Công cụ tìm kiếm & tính toán (gọi core/)
    nodes.py   → 5 node xử lý suy luận (gọi tools + core/llm)
    edges.py   → Logic định tuyến điều kiện
    graph.py   → Compile & export LangGraph workflow

Export công khai duy nhất: admission_graph từ graph.py.
"""
