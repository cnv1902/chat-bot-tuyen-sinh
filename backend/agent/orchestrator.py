"""
agent/orchestrator.py
=====================
Agentic RAG Orchestrator (ReAct / Tool Calling Agent).
Thay thế cho luồng LangGraph 5-node cũ.
"""

import logging
from typing import Any

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from agent.tools import query_admission_data, search_unstructured_knowledge, check_admission_eligibility
from llm import get_langchain_chat_model

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là chuyên gia tư vấn tuyển sinh ĐH Vinh. Hãy phân tích kỹ câu hỏi. 

Mệnh lệnh 1: Nếu thí sinh cung cấp điểm số cá nhân cụ thể và hỏi 'Em có đỗ không?', 'Điểm của em thế này đỗ không?', BẮT BUỘC phải dùng công cụ check_admission_eligibility để thẩm định.
Mệnh lệnh 2: Nếu thí sinh chỉ hỏi thông tin chung như 'Ngành IT lấy bao nhiêu điểm?', 'Chỉ tiêu bao nhiêu?', dùng công cụ query_admission_data.

Nếu hỏi mô tả/đời sống/điều kiện, dùng search_unstructured_knowledge. 
Nếu hỏi cả hai, gọi tuần tự. 
Tuyệt đối không tự tính toán hệ số điểm hay điểm ưu tiên, hãy phó thác hoàn toàn cho công cụ.
Chỉ trả lời dựa trên kết quả Tool. 
Nếu không có dữ liệu, hãy xin SĐT để cán bộ liên hệ.
Hãy trả lời thân thiện, mạch lạc, dễ hiểu."""

async def run_agent(user_message: str, chat_history: list[dict], session_id: str) -> tuple[str, list[str]]:
    """
    Thực thi Agent với tool calling và trả về (câu trả lời, danh sách nguồn).
    """
    logger.info(f"[Orchestrator] Khởi chạy Agent cho session {session_id}")
    
    # Lấy LLM
    try:
        llm = await get_langchain_chat_model()
    except Exception as e:
        logger.error(f"[Orchestrator] Lỗi lấy LLM: {str(e)}")
        return "Hệ thống đang bảo trì phần trí tuệ nhân tạo. Vui lòng quay lại sau.", []

    # Khởi tạo tools
    tools = [query_admission_data, search_unstructured_knowledge, check_admission_eligibility]

    import datetime
    current_year = datetime.datetime.now().year
    dynamic_system_prompt = SYSTEM_PROMPT + f"\nLưu ý thời gian thực: Năm nay là {current_year}. Nếu người dùng dùng các từ như 'năm nay', 'hiện tại', hãy tự động hiểu là {current_year}, 'năm ngoái' là {current_year - 1}."

    # Khởi tạo Agent sử dụng LangGraph prebuilt
    try:
        agent = create_react_agent(llm, tools, prompt=dynamic_system_prompt)
    except Exception as e:
        logger.error(f"[Orchestrator] Lỗi khởi tạo agent: {str(e)}")
        return "Xin lỗi, đã có sự cố trong quá trình thiết lập hệ thống tư vấn.", []

    # Chuyển đổi lịch sử chat
    langchain_history = []
    for msg in chat_history:
        if msg.get("role") == "user":
            langchain_history.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            langchain_history.append(AIMessage(content=msg.get("content", "")))

    langchain_history.append(HumanMessage(content=user_message))

    # Thực thi
    try:
        response = await agent.ainvoke({"messages": langchain_history})
        
        # Output là list messages
        messages = response.get("messages", [])
        if not messages:
            return "Không thể tạo ra câu trả lời.", []
            
        answer = messages[-1].content
        
        # Trích xuất nguồn từ các tool call messages
        sources = []
        import re
        for msg in messages:
            # Tìm các ToolMessage chứa nguồn
            if hasattr(msg, 'name') and msg.name in ["search_unstructured_knowledge", "query_admission_data"]:
                content = str(msg.content)
                found_sources = re.findall(r"--- Nguồn: (.*?) ---", content)
                sources.extend(found_sources)
                    
        # Deduplicate sources
        unique_sources = list(dict.fromkeys(sources))
        
        return answer, unique_sources
    except Exception as e:
        logger.error(f"[Orchestrator] Lỗi khi invoke agent: {str(e)}")
        return "Xin lỗi, đã xảy ra lỗi trong quá trình xử lý. Vui lòng thử lại sau.", []
