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
from core.session import get_history, save_history
from core.interceptor_service import check_interceptor
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
    
    # ── [3] Chạy Agent Orchestrator ──
    try:
        # AgentExecutor ainvoke sử dụng main loop, nhưng có thể sinh ra I/O.
        # Chúng ta dùng await trực tiếp vì LangChain model async hỗ trợ non-blocking.
        bot_answer, sources = await run_agent(req.message, chat_history, req.session_id)
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
    )
