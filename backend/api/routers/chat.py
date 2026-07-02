"""
api/routers/chat.py
===================
Endpoint chính: POST /api/chat — Cổng giao tiếp của Agentic RAG.
"""

import logging
import time
import uuid
import re
import random
import asyncio

from fastapi import APIRouter, HTTPException, Request, status, BackgroundTasks

from agent.orchestrator import run_agent
from api.schemas import ChatRequest, ChatResponse
from core.session import get_history, save_history, get_handoff_session, save_handoff_session
from core.interceptor_service import check_interceptor
from core.event_bus import (
    publish_support_event, 
    subscribe_candidate_events, 
    unsubscribe_candidate_events
)
from db.connection import get_db, AsyncSessionLocal
from db.crud import get_slot
from llm import get_langchain_chat_model
from db.models import QAStaging
from langchain_core.messages import HumanMessage, SystemMessage
from core.event_bus import publish_qa_event
from core.embedder import embed
from core.vectordb import search_qa_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])

async def summarize_history_task(session_id: str, chat_history: list[dict]):
    """Background task tóm tắt lịch sử nếu vượt quá 6 messages."""
    if len(chat_history) <= 6:
        return
        
    try:
        # Lấy LLM
        llm = await get_langchain_chat_model()
        
        # Tách lịch sử cũ (bỏ 4 messages cuối cùng ~ 2 lượt)
        old_history = chat_history[:-4]
        recent_history = chat_history[-4:]
        
        # Chuẩn bị prompt tóm tắt
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in old_history])
        prompt = (
            "Hãy tóm tắt ngắn gọn (trong 1-2 câu) nội dung chính của phần lịch sử trò chuyện sau giữa người dùng và trợ lý tư vấn tuyển sinh đại học.\n\n"
            f"Lịch sử:\n{history_text}\n\n"
            "Chỉ trả về câu tóm tắt, không giải thích."
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary_text = response.content
        
        # Cập nhật lịch sử mới
        new_history = [{"role": "system", "content": f"[Tóm tắt lịch sử: {summary_text}]"}] + recent_history
        save_history(session_id, new_history)
        logger.info(f"[Summarize] Đã tóm tắt lịch sử thành công cho session {session_id}")
        
    except Exception as e:
        logger.error(f"[Summarize] Lỗi khi tóm tắt lịch sử: {str(e)}")

# ---------------------------------------------------------------------------
# Endpoint: POST /api/chat
# ---------------------------------------------------------------------------

async def save_qa_staging_task(question: str, answer: str) -> None:
    """Background task lưu lại Q&A vào bảng qa_staging để duyệt"""
    try:
        async with AsyncSessionLocal() as db:
            new_qa = QAStaging(
                question=question,
                answer=answer,
                status="pending"
            )
            db.add(new_qa)
            await db.commit()
            logger.info("[QAStaging] Đã lưu Q&A vào hàng đợi chờ duyệt")
            
            # Publish event via SSE
            await publish_qa_event("new_qa", {"id": new_qa.id})
    except Exception as e:
        logger.error("[QAStaging] Lỗi lưu Q&A staging: %s", str(e))

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Gửi câu hỏi tuyển sinh và nhận câu trả lời từ chatbot",
    description="Endpoint chính của Chatbot Tuyển sinh ĐH Vinh. Nhận câu hỏi, chạy Agentic RAG và trả về câu trả lời.",
)
async def chat_endpoint(req: ChatRequest, request: Request, background_tasks: BackgroundTasks) -> ChatResponse:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    start_time = time.perf_counter()

    logger.info(
        "[Chat/%s] ═══ REQUEST ═══ session=%s | msg=%r",
        request_id,
        req.session_id,
        req.message[:80] + ("..." if len(req.message) > 80 else ""),
        req.message[:80] + ("..." if len(req.message) > 80 else ""),
    )

    # ── [0] Handoff Bypass Check ──
    # Kiểm tra xem session này có đang trong chế độ Handoff (trò chuyện 2 chiều) không
    handoff_session = get_handoff_session(req.session_id)
    if handoff_session:
        logger.info(f"[Chat/{request_id}] Bypass LLM: Session đang ở chế độ Handoff.")
        
        # Thêm tin nhắn của Thí sinh vào lịch sử Handoff
        msg = {
            "id": int(time.time() * 1000),
            "sender": "candidate",
            "text": req.message,
            "time": "Vừa xong"
        }
        handoff_session["history"] = handoff_session.get("history", [])
        handoff_session["history"].append(msg)
        handoff_session["updated_at"] = time.time()
        handoff_session["last_message"] = req.message
        save_handoff_session(req.session_id, handoff_session)
        
        # Bắn SSE sang cho Cán bộ (Admin)
        await publish_support_event("new_message", {"session_id": req.session_id, "message": msg})
        
        return ChatResponse(
            session_id=req.session_id,
            answer="", # Trả về rỗng vì UI Thí sinh sẽ dùng SSE hoặc hiển thị trực tiếp
            sources=[],
        )

    # ── [1] Greeting & Toxic Interceptor ──
    interceptor_answer = check_interceptor(req.message)
    if interceptor_answer:
        logger.info("[Chat/%s] Intercepted: '%s'", request_id, req.message)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000)
        
        # Vẫn lấy và cập nhật lịch sử để giao tiếp tự nhiên
        chat_history = get_history(req.session_id)
        chat_history.append({"role": "user", "content": req.message})
        chat_history.append({"role": "assistant", "content": interceptor_answer})
        
        # Trigger summarize if needed
        if len(chat_history) > 6:
            background_tasks.add_task(summarize_history_task, req.session_id, chat_history.copy())
        else:
            save_history(req.session_id, chat_history)
        
        return ChatResponse(
            session_id=req.session_id,
            answer=interceptor_answer,
            sources=[],
        )

    # ── [1.5] Semantic Cache Check ──
    try:
        query_vector = embed(req.message)
        cached_qa = search_qa_cache(query_vector, score_threshold=0.85)
        
        if cached_qa:
            logger.info("[Chat/%s] ⚡ Phản hồi tức thì từ Semantic Cache.", request_id)
            
            chat_history = get_history(req.session_id)
            chat_history.append({"role": "user", "content": req.message})
            chat_history.append({"role": "assistant", "content": cached_qa.get("answer", "")})
            
            if len(chat_history) > 6:
                background_tasks.add_task(summarize_history_task, req.session_id, chat_history.copy())
            else:
                save_history(req.session_id, chat_history)
                
            return ChatResponse(
                session_id=req.session_id,
                answer=cached_qa.get("answer", ""),
                sources=["Semantic Cache"],
            )
    except Exception as e:
        logger.warning("[Chat/%s] Lỗi kiểm tra Semantic Cache: %s", request_id, str(e))

    # ── [2] Lấy lịch sử từ Redis ──
    chat_history = get_history(req.session_id)
    
    handoff_data = {}
    
    # ── [3] Chạy Agent Orchestrator ──
    try:
        # AgentExecutor ainvoke sử dụng main loop, nhưng có thể sinh ra I/O.
        # Chúng ta dùng await trực tiếp vì LangChain model async hỗ trợ non-blocking.
        from agent.orchestrator import HandoffTriggeredException
        bot_answer, sources, handoff_data = await run_agent(req.message, chat_history, req.session_id)
    except HandoffTriggeredException as e:
        logger.info("[Chat/%s] Đã ngắt luồng sớm do Handoff kích hoạt.", request_id)
        handoff_data = e.handoff_data
        bot_answer = "Hệ thống đang kết nối bạn với Tư vấn viên thực tế..."
        sources = []
        # Gửi cảnh báo realtime xuống Admin
        payload = {
            "session_id": req.session_id,
            "candidate_name": "Thí sinh Khách",
            "last_message": req.message,
            "time": "Vừa xong",
            "major": handoff_data.get("staff_info", {}).get("major", "Chưa rõ") if handoff_data.get("staff_info") else "Chưa rõ",
            "staff_info": handoff_data.get("staff_info"),
            "history": []
        }
        # Lưu vào Redis để đánh dấu bắt đầu chat 2 chiều
        save_handoff_session(req.session_id, payload)
        
        await publish_support_event("handoff_request", payload)
    except Exception as e:
        logger.error(
            "[Chat/%s] Agent pipeline THẤT BẠI: %s",
            request_id, str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hệ thống tạm thời gặp sự cố kỹ thuật. Vui lòng thử lại sau.",
        )

    # Strip thinking trace nếu có (cho reasoning model)
    bot_answer = re.sub(r'<think>.*?</think>', '', bot_answer, flags=re.DOTALL).strip()

    if not bot_answer:
        bot_answer = "Xin lỗi, hệ thống tạm thời không thể xử lý câu hỏi này."

    # ── [4] Cập nhật lịch sử ──
    chat_history.append({"role": "user", "content": req.message})
    chat_history.append({"role": "assistant", "content": bot_answer})
    
    # ── [4.1] Gọi Background Task tóm tắt lịch sử ──
    if len(chat_history) > 6:
        background_tasks.add_task(summarize_history_task, req.session_id, chat_history.copy())
    else:
        save_ok = save_history(req.session_id, chat_history)
        if not save_ok:
            logger.warning("[Chat/%s] Lỗi lưu Redis.", request_id)

    # ── [4.2] Lưu Q&A vào bảng staging ──
    background_tasks.add_task(save_qa_staging_task, req.message, bot_answer)

    # ── [5] Trả response ──
    elapsed_ms = round((time.perf_counter() - start_time) * 1000)
    logger.info(
        "[Chat/%s] ═══ HOÀN THÀNH ═══ %dms | sources=%d | answer=%d ký tự",
        request_id,
        elapsed_ms,
        len(sources),
        len(bot_answer),
    )

    return ChatResponse(
        session_id=req.session_id,
        answer=bot_answer,
        sources=sources,
        handoff_triggered=bool(handoff_data),
        staff_info=handoff_data.get("staff_info") if handoff_data else None
    )

@router.get("/chat/stream/{session_id}")
async def candidate_stream(session_id: str, request: Request):
    """
    Endpoint SSE cho phép Thí sinh kết nối và nhận tin nhắn realtime từ Cán bộ.
    """
    from fastapi.responses import StreamingResponse
    import json
    
    queue = await subscribe_candidate_events(session_id)
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    pass
        finally:
            unsubscribe_candidate_events(session_id)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

from pydantic import BaseModel

class EndHandoffRequest(BaseModel):
    session_id: str

@router.post("/chat/end-handoff")
async def candidate_end_handoff(req: EndHandoffRequest):
    """Thí sinh chủ động kết thúc phiên Handoff."""
    from core.session import delete_handoff_session
    from core.event_bus import publish_support_event
    
    delete_handoff_session(req.session_id)
    
    # Báo cho Admin biết
    await publish_support_event("handoff_ended", {"session_id": req.session_id})
    return {"success": True}
