"""
api/routers/health.py
=====================
Endpoint kiểm tra trạng thái hệ thống: GET /health

Kiểm tra tuần tự 3 thành phần hạ tầng:
    [1] Redis   — ping + đo latency
    [2] Qdrant  — kiểm tra collection tồn tại
    [3] Embedder — xác nhận model đã load và trả về dimension

Trạng thái tổng thể:
    "ok"       — Tất cả components hoạt động bình thường
    "degraded" — Ít nhất 1 component bị lỗi nhưng hệ thống vẫn hoạt động một phần
    "error"    — Lỗi nghiêm trọng không thể phục vụ request

HTTP Status Code:
    200 → ok | degraded (vẫn serve traffic, monitoring tự cảnh báo)
    503 → error          (load balancer ngừng route traffic vào instance này)
"""

import logging
import os

from fastapi import APIRouter, Response, status

from api.schemas import HealthResponse
from core.session import health_check as redis_health_check

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái hệ thống",
    description=(
        "Kiểm tra kết nối Redis, Qdrant và trạng thái Embedding Model. "
        "Dùng cho load balancer health probe và monitoring dashboard."
    ),
)
async def health_check(response: Response) -> HealthResponse:
    """
    Thực hiện health check tuần tự cho từng component.

    Args:
        response: FastAPI Response object — để set HTTP status code động.

    Returns:
        HealthResponse với status tổng thể và chi tiết từng component.
    """
    components: dict = {}
    has_error = False
    has_warning = False

    # ── [1] Kiểm tra Redis ──
    try:
        redis_result = redis_health_check()
        components["redis"] = redis_result

        if redis_result.get("status") != "ok":
            has_warning = True
            logger.warning(
                "[Health] Redis không ổn định: %s", redis_result.get("detail", "")
            )
        else:
            logger.debug("[Health] Redis OK | latency=%.2fms", redis_result.get("latency_ms", 0))

    except Exception as e:
        components["redis"] = {"status": "error", "detail": str(e)}
        has_warning = True
        logger.error("[Health] Redis check thất bại: %s", str(e))

    # ── [2] Kiểm tra Qdrant ──
    try:
        from core.vectordb import _get_client as qdrant_client, get_collection_name

        client = qdrant_client()
        collection_name = get_collection_name()
        collection_exists = client.collection_exists(collection_name)

        if collection_exists:
            # Lấy thêm thông tin collection (số vectors)
            info = client.get_collection(collection_name)
            vectors_count = getattr(
                getattr(info, "vectors_count", None), "__class__", type(None)
            )
            # Truy cập an toàn vào vectors_count
            vc = info.vectors_count if hasattr(info, "vectors_count") else "N/A"
            components["qdrant"] = {
                "status":           "ok",
                "collection":       collection_name,
                "vectors_count":    vc,
            }
            logger.debug(
                "[Health] Qdrant OK | collection=%s | vectors=%s",
                collection_name, vc,
            )
        else:
            components["qdrant"] = {
                "status":     "warning",
                "collection": collection_name,
                "detail":     f"Collection '{collection_name}' chưa tồn tại. "
                              "Cần chạy indexing pipeline trước.",
            }
            has_warning = True
            logger.warning(
                "[Health] Qdrant: collection '%s' chưa tồn tại.", collection_name
            )

    except Exception as e:
        components["qdrant"] = {"status": "error", "detail": str(e)}
        has_error = True
        logger.error("[Health] Qdrant check thất bại: %s", str(e), exc_info=True)

    # ── [3] Kiểm tra Embedding Model ──
    try:
        from core.embedder import get_embedding_dimension, _get_model

        # _get_model() dùng singleton — không load lại nếu đã có trong RAM
        # Nếu chưa warmup: lần đầu gọi health check sẽ trigger load (~3-8s)
        model_name = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
        dimension = get_embedding_dimension()

        components["embedder"] = {
            "status":    "ok",
            "model":     model_name,
            "dimension": dimension,
        }
        logger.debug(
            "[Health] Embedder OK | model=%s | dim=%d", model_name, dimension
        )

    except Exception as e:
        components["embedder"] = {
            "status": "error",
            "detail": str(e),
            "model":  os.getenv("EMBED_MODEL", "BAAI/bge-m3"),
        }
        has_error = True
        logger.error(
            "[Health] Embedder check thất bại: %s", str(e), exc_info=True
        )

    # ── Xác định trạng thái tổng thể ──
    if has_error:
        overall_status = "error"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.error("[Health] Trạng thái tổng thể: ERROR")
    elif has_warning:
        overall_status = "degraded"
        response.status_code = status.HTTP_200_OK  # Vẫn 200 để LB không cut traffic
        logger.warning("[Health] Trạng thái tổng thể: DEGRADED")
    else:
        overall_status = "ok"
        response.status_code = status.HTTP_200_OK
        logger.info("[Health] Trạng thái tổng thể: OK")

    return HealthResponse(status=overall_status, components=components)
