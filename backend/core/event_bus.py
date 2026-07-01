import asyncio
import logging
from typing import Set

logger = logging.getLogger(__name__)

# Global state to store all active SSE client queues
qa_event_queues: Set[asyncio.Queue] = set()

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
