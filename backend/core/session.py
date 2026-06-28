"""
core/session.py
===============
Redis Session Manager — Lịch sử hội thoại với Race Condition Protection.

Thiết kế & Giải pháp Race Condition:
=========================================
VẤN ĐỀ: Nếu cùng session_id gửi 2 request đồng thời:
    Thread A: đọc history=[msg1, msg2] → xử lý → ghi=[msg1,msg2,msgA]
    Thread B: đọc history=[msg1, msg2] → xử lý → ghi=[msg1,msg2,msgB]
    → msgA bị mất hoàn toàn (last-write-wins race condition)

GIẢI PHÁP — Redis Pipeline với WATCH (Optimistic Locking):
    1. WATCH key → bắt đầu giám sát
    2. GET current value
    3. MULTI → bắt đầu transaction block
    4. SET new value
    5. EXEC → thực thi; tự động FAIL nếu key bị sửa bởi client khác
       giữa bước 1 và bước 5
    6. Retry tối đa MAX_RETRIES lần nếu bị conflict

Graceful Degradation:
    - Mọi hàm đều try/except RedisError
    - get_history() trả về [] thay vì raise khi Redis down
    - save_history() log warning và tiếp tục thay vì crash
    → API chat vẫn hoạt động (không lưu được history) khi Redis tạm thời down
"""

import json
import logging
import os
from typing import Optional

import redis
from redis.exceptions import RedisError, WatchError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

MAX_RETRIES = 3          # Số lần retry tối đa khi gặp WatchError
SESSION_KEY_PREFIX = "chat:session:"  # Namespace Redis key để tránh xung đột


# ---------------------------------------------------------------------------
# Connection Pool Singleton
# ---------------------------------------------------------------------------

_redis_pool: Optional[redis.ConnectionPool] = None


def _get_pool() -> redis.ConnectionPool:
    """
    Trả về Redis ConnectionPool duy nhất (module-level singleton).
    ConnectionPool tái dụng connections thay vì tạo TCP connection mới
    cho mỗi operation — giảm latency đáng kể.

    Returns:
        redis.ConnectionPool đã cấu hình.
    """
    global _redis_pool
    if _redis_pool is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
        db_index = int(os.getenv("REDIS_DB", "0"))

        logger.info("[Session] Khởi tạo Redis ConnectionPool → %s | db=%d", redis_url, db_index)
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            db=db_index,
            max_connections=20,           # Tối đa 20 connections đồng thời
            decode_responses=True,        # Tự động decode bytes → str (UTF-8)
            socket_timeout=5,             # Timeout đọc: 5 giây
            socket_connect_timeout=3,     # Timeout kết nối: 3 giây
            retry_on_timeout=True,        # Tự retry khi timeout (không phải lỗi data)
        )
    return _redis_pool


def _get_client() -> redis.Redis:
    """
    Tạo Redis client từ pool đã có (không tạo connection mới nếu pool còn slot).

    Returns:
        redis.Redis client sẵn sàng sử dụng.
    """
    return redis.Redis(connection_pool=_get_pool())


def _session_key(session_id: str) -> str:
    """Tạo Redis key đầy đủ với namespace prefix."""
    return f"{SESSION_KEY_PREFIX}{session_id}"


def _get_ttl() -> int:
    """Đọc TTL phiên chat từ biến môi trường (giây)."""
    return int(os.getenv("SESSION_TTL_SECONDS", "1800"))


# ---------------------------------------------------------------------------
# Serialization Helpers — Đảm bảo Unicode tiếng Việt
# ---------------------------------------------------------------------------

def _serialize(history: list[dict]) -> str:
    """
    Serialize danh sách messages sang JSON string.
    ensure_ascii=False bắt buộc để giữ nguyên ký tự tiếng Việt
    (tránh bị escape thành \\uXXXX gây khó debug và tăng dung lượng).
    """
    return json.dumps(history, ensure_ascii=False, separators=(",", ":"))


def _deserialize(raw: str | None) -> list[dict]:
    """
    Deserialize JSON string từ Redis về list[dict].
    Trả về [] nếu raw là None hoặc JSON bị corrupt.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        logger.warning("[Session] Dữ liệu Redis không phải list: %s", type(data))
        return []
    except json.JSONDecodeError as e:
        logger.error("[Session] Lỗi JSON decode lịch sử chat: %s", str(e))
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_history(session_id: str) -> list[dict]:
    """
    Lấy lịch sử hội thoại của một phiên từ Redis.

    Đồng thời làm mới TTL của session để phiên không hết hạn
    trong khi người dùng đang nhập tin nhắn dài.

    Args:
        session_id: UUID định danh phiên chat của người dùng.

    Returns:
        Danh sách messages theo format:
        [{"role": "user"|"assistant", "content": "..."}]
        Trả về [] nếu phiên chưa tồn tại hoặc Redis không khả dụng.
    """
    key = _session_key(session_id)
    try:
        client = _get_client()

        # Dùng pipeline để GET + EXPIRE trong 1 round-trip (atomic hơn)
        with client.pipeline(transaction=False) as pipe:
            pipe.get(key)
            pipe.expire(key, _get_ttl())     # Làm mới TTL mỗi lần đọc
            results = pipe.execute()

        raw_data = results[0]                # Kết quả của GET
        history = _deserialize(raw_data)

        logger.debug(
            "[Session] get_history(%s) → %d messages.", session_id, len(history)
        )
        return history

    except RedisError as e:
        logger.warning(
            "[Session] Redis không khả dụng, trả về history rỗng: %s", str(e)
        )
        return []
    except Exception as e:
        logger.error(
            "[Session] Lỗi không xác định get_history(%s): %s",
            session_id, str(e), exc_info=True,
        )
        return []


def save_history(session_id: str, history: list[dict]) -> bool:
    """
    Lưu lịch sử hội thoại vào Redis với bảo vệ Race Condition.

    Dùng Optimistic Locking (WATCH + MULTI/EXEC):
    - WATCH giám sát key, nếu bị sửa bởi request khác → EXEC tự fail
    - Retry tối đa MAX_RETRIES lần khi bị conflict
    - Sau MAX_RETRIES lần fail → log error + bỏ qua (graceful degradation)

    Args:
        session_id: UUID phiên chat.
        history:    Danh sách messages đầy đủ cần lưu (đã cắt giới hạn ở caller).

    Returns:
        True nếu lưu thành công, False nếu thất bại.
    """
    key = _session_key(session_id)
    serialized = _serialize(history)
    ttl = _get_ttl()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _get_client()

            with client.pipeline() as pipe:
                try:
                    # --- Bước 1: Bắt đầu WATCH key ---
                    pipe.watch(key)

                    # --- Bước 2: MULTI — bắt đầu transaction block ---
                    pipe.multi()

                    # --- Bước 3: Ghi giá trị mới ---
                    pipe.set(key, serialized, ex=ttl)

                    # --- Bước 4: EXEC — thực thi transaction ---
                    # Nếu key bị thay đổi bởi client khác giữa WATCH và EXEC
                    # → WatchError tự động được raise
                    pipe.execute()

                    logger.debug(
                        "[Session] save_history(%s) thành công | %d messages | "
                        "attempt=%d",
                        session_id, len(history), attempt,
                    )
                    return True

                except WatchError:
                    # Key bị sửa bởi request đồng thời → retry
                    logger.warning(
                        "[Session] WatchError lần %d/%d cho session '%s' — retry...",
                        attempt, MAX_RETRIES, session_id,
                    )
                    if attempt == MAX_RETRIES:
                        logger.error(
                            "[Session] Đã hết %d lần retry cho session '%s'. "
                            "Lịch sử KHÔNG được lưu lần này.",
                            MAX_RETRIES, session_id,
                        )
                        return False
                    continue

        except RedisError as e:
            logger.warning(
                "[Session] Redis không khả dụng khi save_history(%s): %s",
                session_id, str(e),
            )
            return False
        except Exception as e:
            logger.error(
                "[Session] Lỗi không xác định save_history(%s): %s",
                session_id, str(e), exc_info=True,
            )
            return False

    return False


def delete_session(session_id: str) -> bool:
    """
    Xóa toàn bộ lịch sử của một phiên chat.
    Dùng khi người dùng bấm "Bắt đầu cuộc trò chuyện mới".

    Args:
        session_id: UUID phiên cần xóa.

    Returns:
        True nếu xóa thành công hoặc key không tồn tại.
        False nếu Redis lỗi.
    """
    key = _session_key(session_id)
    try:
        client = _get_client()
        deleted_count = client.delete(key)
        logger.info(
            "[Session] delete_session(%s) → %d key bị xóa.",
            session_id, deleted_count,
        )
        return True
    except RedisError as e:
        logger.warning(
            "[Session] Redis lỗi khi delete_session(%s): %s", session_id, str(e)
        )
        return False
    except Exception as e:
        logger.error(
            "[Session] Lỗi không xác định delete_session(%s): %s",
            session_id, str(e), exc_info=True,
        )
        return False


def get_session_ttl(session_id: str) -> int:
    """
    Trả về số giây còn lại trước khi phiên hết hạn.
    Hữu ích cho frontend hiển thị thông báo "Phiên sắp hết hạn".

    Returns:
        Số giây còn lại. -2 nếu key không tồn tại. -1 nếu không có TTL.
        0 nếu Redis không khả dụng.
    """
    key = _session_key(session_id)
    try:
        client = _get_client()
        return client.ttl(key)
    except RedisError:
        return 0


def health_check() -> dict:
    """
    Kiểm tra trạng thái kết nối Redis.
    Dùng cho endpoint GET /health.

    Returns:
        {"status": "ok", "latency_ms": float} hoặc
        {"status": "error", "detail": str}
    """
    import time
    try:
        client = _get_client()
        start = time.perf_counter()
        client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except RedisError as e:
        return {"status": "error", "detail": str(e)}
