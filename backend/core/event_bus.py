import asyncio
import logging
from typing import Set, Dict

logger = logging.getLogger(__name__)

# Global state to store all active SSE client queues
qa_event_queues: Set[asyncio.Queue] = set()
support_event_queues: Set[asyncio.Queue] = set()
candidate_event_queues: Dict[str, asyncio.Queue] = {}

async def subscribe_qa_events() -> asyncio.Queue:
    """
    Tạo một Queue mới cho client SSE và đưa vào Global list.
    """
    queue = asyncio.Queue()
    qa_event_queues.add(queue)
    logger.info(f"[EventBus] Client connected to QA Events. Total clients: {len(qa_event_queues)}")
    return queue

def unsubscribe_qa_events(queue: asyncio.Queue) -> None:
    """
    Loại bỏ Queue khi client SSE disconnect.
    """
    if queue in qa_event_queues:
        qa_event_queues.remove(queue)
        logger.info(f"[EventBus] Client disconnected from QA Events. Total clients: {len(qa_event_queues)}")

async def publish_qa_event(event: str, data: dict = None) -> None:
    """
    Broadcast sự kiện cho tất cả các clients đang kết nối.
    """
    if data is None:
        data = {}
        
    payload = {
        "event": event,
        "data": data
    }
    
    # Send event to all active queues
    for queue in qa_event_queues:
        await queue.put(payload)

async def subscribe_support_events() -> asyncio.Queue:
    """
    Tạo một Queue mới cho client SSE Admin Support.
    """
    queue = asyncio.Queue()
    support_event_queues.add(queue)
    logger.info(f"[EventBus] Client connected to Support Events. Total clients: {len(support_event_queues)}")
    return queue

def unsubscribe_support_events(queue: asyncio.Queue) -> None:
    """
    Loại bỏ Queue khi client SSE disconnect.
    """
    if queue in support_event_queues:
        support_event_queues.remove(queue)
        logger.info(f"[EventBus] Client disconnected from Support Events. Total clients: {len(support_event_queues)}")

async def publish_support_event(event: str, data: dict = None) -> None:
    """
    Broadcast sự kiện cho tất cả các cán bộ (Admin Support) đang kết nối.
    """
    if data is None:
        data = {}
        
    payload = {
        "event": event,
        "data": data
    }
    
    # Send event to all active queues
    for queue in support_event_queues:
        await queue.put(payload)

async def subscribe_candidate_events(session_id: str) -> asyncio.Queue:
    """
    Tạo một Queue mới cho Thí sinh theo session_id.
    """
    queue = asyncio.Queue()
    candidate_event_queues[session_id] = queue
    logger.info(f"[EventBus] Candidate {session_id} connected. Total candidates: {len(candidate_event_queues)}")
    return queue

def unsubscribe_candidate_events(session_id: str) -> None:
    """
    Loại bỏ Queue khi Thí sinh disconnect.
    """
    if session_id in candidate_event_queues:
        del candidate_event_queues[session_id]
        logger.info(f"[EventBus] Candidate {session_id} disconnected. Total candidates: {len(candidate_event_queues)}")

async def publish_candidate_event(session_id: str, event: str, data: dict = None) -> None:
    """
    Gửi sự kiện (tin nhắn) cụ thể cho một Thí sinh.
    """
    if session_id not in candidate_event_queues:
        return
        
    if data is None:
        data = {}
        
    payload = {
        "event": event,
        "data": data
    }
    
    await candidate_event_queues[session_id].put(payload)
