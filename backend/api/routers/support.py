import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

from pydantic import BaseModel
from typing import Any
import time

from core.event_bus import (
    subscribe_support_events, 
    unsubscribe_support_events,
    publish_candidate_event
)
from core.session import (
    get_all_handoff_sessions, 
    get_handoff_session, 
    save_handoff_session, 
    delete_handoff_session
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/support",
    tags=["Admin Support"],
)

@router.get("/stream")
async def support_stream(request: Request):
    """
    Endpoint SSE cho phép Cán bộ (Admin) kết nối và nhận cảnh báo Handoff realtime.
    """
    queue = await subscribe_support_events()
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                # Chờ tối đa 1s để check disconnect thường xuyên
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    pass
        finally:
            unsubscribe_support_events(queue)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/conversations", response_model=dict)
async def get_conversations():
    """Lấy danh sách các phiên chat Handoff đang hoạt động."""
    sessions = get_all_handoff_sessions()
    return {"success": True, "data": sessions}

class SupportMessageRequest(BaseModel):
    session_id: str
    message: str

@router.post("/message", response_model=dict)
async def send_message_to_candidate(req: SupportMessageRequest):
    """Cán bộ gửi tin nhắn cho thí sinh."""
    handoff_data = get_handoff_session(req.session_id)
    if not handoff_data:
        return {"success": False, "error": "Phiên chat đã kết thúc hoặc không tồn tại."}
        
    msg = {
        "id": int(time.time() * 1000),
        "sender": "admin",
        "text": req.message,
        "time": "Vừa xong"
    }
    
    # Cập nhật vào Redis
    handoff_data["history"] = handoff_data.get("history", [])
    handoff_data["history"].append(msg)
    handoff_data["updated_at"] = time.time()
    handoff_data["lastMessage"] = req.message
    save_handoff_session(req.session_id, handoff_data)
    
    # Bắn SSE sang Thí sinh
    await publish_candidate_event(req.session_id, "new_message", {"message": msg})
    
    return {"success": True, "data": msg}

@router.post("/end-handoff", response_model=dict)
async def end_handoff(req: SupportMessageRequest):
    """Cán bộ kết thúc phiên chat."""
    delete_handoff_session(req.session_id)
    
    # Báo cho Thí sinh biết Cán bộ đã tắt chat
    await publish_candidate_event(req.session_id, "handoff_ended", {"message": "Cán bộ đã kết thúc phiên hỗ trợ. Bạn hiện đang trò chuyện với Trợ lý ảo AI."})
    
    return {"success": True}
