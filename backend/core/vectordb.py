"""
core/vectordb.py
================
Qdrant Vector Database Client — Connection Pool & Filter Builder.

Thiết kế:
- Singleton QdrantClient qua module-level instance (thread-safe vì
  qdrant-client đã tích hợp connection pool nội bộ).
- `build_filter()`: Dịch dict filters từ agent sang Qdrant Filter object
  theo API chính xác của qdrant-client v1.9+.
  - string fields (doc_type) → MatchValue
  - integer fields (year)    → MatchValue (int)
  - Bỏ qua giá trị None để không bị lỗi filter rỗng.
- `search()`: Trả về list[dict] chuẩn hóa để agent không cần biết
  về internals của Qdrant.
- `setup_collection()` + `upsert_points()`: Phục vụ indexing pipeline.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kiểu filter mà agent truyền vào — mapping sang Qdrant condition types
# ---------------------------------------------------------------------------
# Ví dụ dynamic_filters từ classify_intent:
# {
#   "year": 2026,          → MatchValue(value=2026) trên field "year"
#   "doc_type": "diem_chuan", → MatchValue(value="diem_chuan") trên "doc_type"
# }
#
# Các field này phải khớp CHÍNH XÁC với payload keys được lưu trong Qdrant
# (xem indexer.py: payload={'content': ..., 'year': ..., 'doc_type': ..., ...})
# ---------------------------------------------------------------------------

# Mapping: tên filter field → kiểu dữ liệu mong đợi để cast đúng type
_FILTER_FIELD_TYPES: dict[str, type] = {
    "year":     int,
    "doc_type": str,
}


# ---------------------------------------------------------------------------
# Singleton Client
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_client() -> QdrantClient:
    """
    Khởi tạo và trả về QdrantClient duy nhất.
    lru_cache đảm bảo connection pool được tái dụng — không tạo
    connection mới mỗi request.

    Returns:
        QdrantClient đã kết nối tới Qdrant instance.

    Raises:
        ConnectionError: Nếu không thể kết nối tới Qdrant server.
    """
    host = os.getenv("QDRANT_HOST", "localhost").strip()
    port = int(os.getenv("QDRANT_PORT", "6333"))
    api_key = os.getenv("QDRANT_API_KEY", "").strip() or None  # None nếu rỗng

    logger.info("[VectorDB] Khởi tạo QdrantClient → %s:%d", host, port)

    try:
        client = QdrantClient(
            host=host,
            port=port,
            api_key=api_key,
            timeout=10,          # Timeout 10 giây cho mỗi request
            prefer_grpc=False,   # Dùng REST API — ổn định hơn khi qua Docker
        )
        # Ping để xác nhận kết nối ngay khi khởi tạo
        client.get_collections()
        logger.info("[VectorDB] Kết nối Qdrant thành công.")
        return client
    except Exception as e:
        logger.critical(
            "[VectorDB] KHÔNG THỂ kết nối Qdrant tại %s:%d — %s",
            host, port, str(e),
        )
        raise ConnectionError(
            f"Không thể kết nối Qdrant tại {host}:{port}. "
            f"Hãy kiểm tra Docker đang chạy. Lỗi: {e}"
        ) from e


def get_collection_name() -> str:
    """Trả về tên collection từ biến môi trường."""
    return os.getenv("QDRANT_COLLECTION", "tuyen_sinh_dhv").strip()


# ---------------------------------------------------------------------------
# Filter Builder — Chuyển dict → Qdrant Filter object
# ---------------------------------------------------------------------------

def _build_filter(filters: dict[str, Any]) -> Optional[qmodels.Filter]:
    """
    Dịch dict filters (từ agent) sang `qdrant_client.models.Filter`.

    Xử lý 2 loại field:
    - `year` (int)      → MatchValue với giá trị integer
    - `doc_type` (str)  → MatchValue với giá trị chuỗi

    Args:
        filters: Dict với keys tùy chọn: year, doc_type.
                 Các key có value là None sẽ bị bỏ qua hoàn toàn.

    Returns:
        `qmodels.Filter` object nếu có ít nhất 1 điều kiện hợp lệ.
        `None` nếu không có filter nào — Qdrant sẽ search toàn bộ collection.

    Example:
        >>> _build_filter({"year": 2026, "doc_type": "diem_chuan"})
        Filter(must=[
            FieldCondition(key="year",     match=MatchValue(value=2026)),
            FieldCondition(key="doc_type", match=MatchValue(value="diem_chuan")),
        ])
    """
    if not filters:
        return None

    must_conditions: list[qmodels.FieldCondition] = []

    for field, raw_value in filters.items():
        # Bỏ qua giá trị None, rỗng hoặc field không được định nghĩa
        if raw_value is None:
            continue
        if isinstance(raw_value, str) and not raw_value.strip():
            continue
        if field not in _FILTER_FIELD_TYPES:
            logger.warning(
                "[VectorDB] Filter field '%s' không được hỗ trợ — bỏ qua.", field
            )
            continue

        try:
            # Cast sang đúng kiểu dữ liệu của field
            expected_type = _FILTER_FIELD_TYPES[field]
            typed_value = expected_type(raw_value)

            must_conditions.append(
                qmodels.FieldCondition(
                    key=field,
                    match=qmodels.MatchValue(value=typed_value),
                )
            )
            logger.debug(
                "[VectorDB] Thêm filter: %s = %r (%s)",
                field, typed_value, expected_type.__name__,
            )

        except (ValueError, TypeError) as cast_err:
            logger.warning(
                "[VectorDB] Không thể cast filter '%s'=%r sang %s: %s — bỏ qua.",
                field, raw_value, _FILTER_FIELD_TYPES[field].__name__, cast_err,
            )
            continue

    if not must_conditions:
        return None

    return qmodels.Filter(must=must_conditions)


# ---------------------------------------------------------------------------
# Search — Core Function cho Real-time Inference
# ---------------------------------------------------------------------------

def search(
    query_vector: list[float],
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    score_threshold: float = 0.3,
) -> list[dict]:
    """
    Tìm kiếm semantic các chunks liên quan nhất trong Qdrant.

    Chiến lược Hybrid Search:
    - Hard filter: Áp dụng metadata filter (year, doc_type) trước
      để thu hẹp không gian tìm kiếm.
    - Soft search: Cosine similarity trên vector embedding trong không gian đã lọc.

    Args:
        query_vector:    Vector embedding của câu hỏi người dùng (dim 1024).
        filters:         Dict metadata filter từ agent (None = không filter).
        top_k:           Số lượng kết quả trả về tối đa.
        score_threshold: Ngưỡng similarity tối thiểu — loại bỏ kết quả quá kém.
                         0.3 là ngưỡng thực nghiệm tốt với bge-m3 + Cosine.

    Returns:
        List[dict] chuẩn hóa, mỗi phần tử gồm:
        {
            "content":  str,           # Nội dung chunk
            "score":    float,         # Cosine similarity score [0, 1]
            "metadata": dict           # Toàn bộ payload từ Qdrant (trừ content)
        }
        Trả về [] nếu không tìm thấy hoặc có lỗi.
    """
    try:
        client = _get_client()
        collection = get_collection_name()
        qdrant_filter = _build_filter(filters or {})

        logger.debug(
            "[VectorDB] Search | collection=%s | top_k=%d | filter=%s",
            collection,
            top_k,
            qdrant_filter,
        )

        # query_points — API chính thức từ qdrant-client v1.7+
        # .search() đã bị deprecated và removed trong bản mới
        response = client.query_points(
            collection_name=collection,
            query=query_vector,            # float list — vector embedding
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )

        results = []
        for hit in response.points:        # .points thay vì iterate trực tiếp
            payload = dict(hit.payload or {})
            content = payload.pop("content", "")
            results.append({
                "content":  content,
                "score":    round(hit.score, 4),
                "metadata": payload,
            })

        logger.info(
            "[VectorDB] Tìm thấy %d kết quả (ngưỡng score >= %.2f).",
            len(results), score_threshold,
        )
        return results

    except UnexpectedResponse as e:
        logger.error(
            "[VectorDB] Qdrant trả về response bất thường: %s", str(e), exc_info=True
        )
        return []
    except Exception as e:
        logger.error("[VectorDB] Lỗi search: %s", str(e), exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Collection Management — Phục vụ Indexing Pipeline
# ---------------------------------------------------------------------------

def setup_collection(
    collection_name: str | None = None,
    dimension: int | None = None,
) -> bool:
    """
    Tạo Qdrant collection nếu chưa tồn tại.
    Idempotent: Gọi nhiều lần không có tác dụng phụ.

    Args:
        collection_name: Tên collection (mặc định từ QDRANT_COLLECTION).
        dimension:       Số chiều vector (mặc định từ EMBED_DIMENSION).

    Returns:
        True nếu collection đã sẵn sàng (tạo mới hoặc đã tồn tại từ trước).
        False nếu có lỗi nghiêm trọng.
    """
    name = collection_name or get_collection_name()
    dim = dimension or int(os.getenv("EMBED_DIMENSION", "1024"))

    try:
        client = _get_client()

        if client.collection_exists(name):
            logger.info(
                "[VectorDB] Collection '%s' đã tồn tại — bỏ qua tạo mới.", name
            )
            return True

        client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=dim,
                distance=qmodels.Distance.COSINE,
            ),
            # Tối ưu cho dataset nhỏ-vừa (<1M vectors) — không cần HNSW phức tạp
            optimizers_config=qmodels.OptimizersConfigDiff(
                indexing_threshold=20_000,    # Bắt đầu build index khi có 20k vectors
            ),
        )
        logger.info(
            "[VectorDB] Đã tạo collection '%s' | dim=%d | metric=COSINE.", name, dim
        )

        # Tạo payload indexes để filter nhanh (quan trọng cho performance)
        _create_payload_indexes(client, name)
        return True

    except Exception as e:
        logger.error(
            "[VectorDB] Lỗi tạo collection '%s': %s", name, str(e), exc_info=True
        )
        return False


def _create_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """
    Tạo payload indexes cho các field filter thường dùng.
    Quan trọng cho performance khi filter trên dataset lớn.
    """
    index_fields = [
        ("year",     qmodels.PayloadSchemaType.INTEGER),
        ("doc_type", qmodels.PayloadSchemaType.KEYWORD),
    ]
    for field_name, field_type in index_fields:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type,
            )
            logger.debug(
                "[VectorDB] Đã tạo payload index: '%s' (%s)", field_name, field_type
            )
        except Exception as idx_err:
            # Index có thể đã tồn tại — không phải lỗi nghiêm trọng
            logger.warning(
                "[VectorDB] Bỏ qua tạo index '%s': %s", field_name, str(idx_err)
            )


def upsert_points(
    points: list[qmodels.PointStruct],
    collection_name: str | None = None,
    batch_size: int = 100,
) -> int:
    """
    Đẩy danh sách PointStruct vào Qdrant theo batch.
    Dùng upsert để idempotent (re-index không tạo duplicate).

    Args:
        points:          Danh sách PointStruct đã có id, vector, payload.
        collection_name: Tên collection (mặc định từ env).
        batch_size:      Số points upsert mỗi batch (mặc định 100).

    Returns:
        Số lượng points đã upsert thành công.
    """
    name = collection_name or get_collection_name()
    total_upserted = 0

    try:
        client = _get_client()

        for i in range(0, len(points), batch_size):
            batch = points[i: i + batch_size]
            client.upsert(
                collection_name=name,
                points=batch,
                wait=True,  # Đợi Qdrant xác nhận lưu xong — an toàn hơn
            )
            total_upserted += len(batch)
            logger.debug(
                "[VectorDB] Upsert batch %d-%d/%d thành công.",
                i + 1, i + len(batch), len(points),
            )

        logger.info(
            "[VectorDB] Hoàn thành upsert %d/%d points vào '%s'.",
            total_upserted, len(points), name,
        )
        return total_upserted

    except Exception as e:
        logger.error(
            "[VectorDB] Lỗi upsert points: %s", str(e), exc_info=True
        )
        return total_upserted


# ---------------------------------------------------------------------------
# Delete By Source File — Phục vụ Admin xóa tài liệu
# ---------------------------------------------------------------------------

def delete_points_by_source_file(
    source_file: str,
    collection_name: str | None = None,
) -> int:
    """
    Xóa toàn bộ vector chunks có metadata source_file khớp với tên file.
    
    Sử dụng Qdrant delete_points() với filter theo payload field "source_file".
    Idempotent: gọi nhiều lần không bị lỗi (nếu đã xóa rồi thì count = 0).

    Args:
        source_file:     Tên file cần xóa (ví dụ: "DeAn2026.pdf").
        collection_name: Tên collection (mặc định từ env).

    Returns:
        Số lượng points đã xóa (lấy từ Qdrant info trước và sau xóa).
        Trả về 0 nếu có lỗi hoặc không có points nào.
    """
    name = collection_name or get_collection_name()

    try:
        client = _get_client()

        # Xây filter theo source_file (keyword match)
        points_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="source_file",
                    match=qmodels.MatchValue(value=source_file),
                )
            ]
        )

        # Đếm số points trước khi xóa để report kết quả
        count_before = client.count(
            collection_name=name,
            count_filter=points_filter,
            exact=True,
        ).count

        if count_before == 0:
            logger.info(
                "[VectorDB] Không tìm thấy points nào với source_file=%r — bỏ qua.",
                source_file,
            )
            return 0

        # Thực hiện xóa
        client.delete(
            collection_name=name,
            points_selector=qmodels.FilterSelector(filter=points_filter),
            wait=True,
        )

        logger.info(
            "[VectorDB] Đã xóa %d points có source_file=%r khỏi collection '%s'.",
            count_before, source_file, name,
        )
        return count_before

    except Exception as e:
        logger.error(
            "[VectorDB] Lỗi xóa points theo source_file=%r: %s", source_file, str(e), exc_info=True
        )
        return 0

def delete_points_by_document_id(
    document_id: int,
    collection_name: str | None = None,
) -> int:
    """Xóa points theo document_id"""
    name = collection_name or get_collection_name()
    try:
        client = _get_client()
        points_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id),
                )
            ]
        )
        count_before = client.count(
            collection_name=name,
            count_filter=points_filter,
            exact=True,
        ).count

        if count_before == 0:
            return 0

        client.delete(
            collection_name=name,
            points_selector=qmodels.FilterSelector(filter=points_filter),
            wait=True,
        )
        logger.info("[VectorDB] Đã xóa %d points có document_id=%d", count_before, document_id)
        return count_before
    except Exception as e:
        logger.error("[VectorDB] Lỗi xóa points theo document_id=%d: %s", document_id, str(e))
        return 0
