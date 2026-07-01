"""
indexing/indexer.py
===================
Bước 5: Encode chunks + Upsert vào Qdrant với Content-Hash UUID.

Thiết kế Content-Hash UUID (chống duplicate khi re-index):
    id = UUID(SHA-256(source_file + page + content[:200]))

    Lợi ích:
    - Cùng nội dung → cùng UUID → upsert chỉ UPDATE, không INSERT duplicate
    - Khác nội dung (sửa tài liệu) → UUID mới → INSERT bản mới đúng đắn
    - Idempotent: chạy pipeline lại bất kỳ lúc nào cũng an toàn

    So sánh với UUID4 ngẫu nhiên:
    - UUID4: mỗi lần chạy tạo record mới → collection phình to dần
    - Content-hash: chạy lại N lần = chạy 1 lần về kết quả cuối cùng
"""

import hashlib
import logging
import os
import uuid as uuid_lib
from pathlib import Path

from core.embedder import embed_batch
from qdrant_client import models as qmodels

from indexing.text_utils import normalize_scope, repair_mojibake, repair_text_tree

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Content-Hash UUID
# ---------------------------------------------------------------------------

def _content_hash_uuid(content: str, source_file: str = "", page: int = 0) -> str:
    """
    Sinh UUID v5 deterministic từ nội dung chunk.

    UUID v5 dùng namespace + tên → cùng input luôn cho cùng UUID.
    Điều này đảm bảo tính idempotent khi re-index tài liệu.

    Args:
        content:     Nội dung chunk (dùng 200 ký tự đầu làm fingerprint).
        source_file: Tên file tài liệu gốc.
        page:        Số trang trong tài liệu.

    Returns:
        Chuỗi UUID dạng "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx".
    """
    # Tạo chuỗi fingerprint kết hợp: file + trang + nội dung
    fingerprint = f"{Path(source_file).name}|p{page}|{content[:200].strip()}"
    # Dùng DNS namespace (arbitrary — chỉ cần nhất quán trong project)
    return str(uuid_lib.uuid5(uuid_lib.NAMESPACE_DNS, fingerprint))


# ---------------------------------------------------------------------------
# Model Management (Singleton light — dùng khi chạy standalone)
# ---------------------------------------------------------------------------

_embed_model: SentenceTransformer | None = None


def get_embed_model() -> SentenceTransformer:
    """
    Trả về embedding model singleton cho indexing pipeline.
    Tách khỏi core/embedder.py để indexer có thể chạy độc lập
    mà không cần import toàn bộ FastAPI stack.
    """
    global _embed_model
    if _embed_model is None:
        model_name = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
        device = os.getenv("EMBED_DEVICE", "cpu")
        logger.info("[Indexer] Load embedding model '%s' trên %s...", model_name, device)
        _embed_model = SentenceTransformer(model_name, device=device)
        logger.info("[Indexer] Model loaded | dim=%d", _embed_model.get_sentence_embedding_dimension())
    return _embed_model


# ---------------------------------------------------------------------------
# Core Indexing Functions
# ---------------------------------------------------------------------------

def build_points(
    chunks: list[dict],
    batch_size: int = 32,
) -> list[qmodels.PointStruct]:
    """
    Encode danh sách chunks thành PointStruct với content-hash UUID.

    Args:
        chunks:     Danh sách dict {"content": str, "metadata": dict}.
        batch_size: Số chunk encode mỗi batch.

    Returns:
        Danh sách PointStruct sẵn sàng upsert vào Qdrant.
    """
    if not chunks:
        return []

    normalized_chunks = [_normalize_chunk(chunk) for chunk in chunks]
    texts = [c["content"] for c in normalized_chunks]

    logger.info("[Indexer] Encoding %d chunks (batch_size=%d)...", len(texts), batch_size)
    # Sử dụng embed_batch (đã hỗ trợ Hybrid Dense + Sparse)
    hybrid_vectors = embed_batch(texts, batch_size=batch_size)

    points = []
    for chunk, hybrid_vec in zip(normalized_chunks, hybrid_vectors):
        meta = chunk.get("metadata", {})
        scope = normalize_scope(meta.get("scope", meta.get("faculty", "all")))

        # Content-hash UUID — idempotent khi re-index
        point_id = _content_hash_uuid(
            content=chunk["content"],
            source_file=str(meta.get("source_file", "")),
            page=int(meta.get("page", 0)),
        )

        # Payload = content + tất cả metadata (flat structure cho Qdrant filter)
        payload = {
            "content":     chunk["content"],
            "source_file": repair_mojibake(str(meta.get("source_file", ""))),
            "year":        meta.get("year"),
            "doc_type":    repair_mojibake(str(meta.get("doc_type", "khac"))),
            "scope":       repair_mojibake(str(scope or "all")),
            "page":        int(meta.get("page", 0)),
            "chunk_type":  repair_mojibake(str(meta.get("chunk_type", "paragraph"))),
            "major":       repair_mojibake(str(meta.get("major", ""))),
            "major_code":  repair_mojibake(str(meta.get("major_code", ""))),
        }

        points.append(qmodels.PointStruct(
            id=point_id,
            vector={
                "dense": hybrid_vec["dense"],
                "sparse": qmodels.SparseVector(
                    indices=hybrid_vec["sparse_indices"],
                    values=hybrid_vec["sparse_values"]
                )
            },
            payload=payload,
        ))

    logger.info("[Indexer] Đã tạo %d PointStruct.", len(points))
    return points


def _normalize_chunk(chunk: dict) -> dict:
    """Repair text in chunk content and metadata before embedding/upsert."""
    content = repair_mojibake(str(chunk.get("content", "")))
    metadata = repair_text_tree(chunk.get("metadata", {}))
    if not isinstance(metadata, dict):
        metadata = {}
    return {"content": content, "metadata": metadata}


def index_chunks(
    chunks: list[dict],
    qdrant_client,
    collection: str,
    batch_size: int = 100,
) -> int:
    """
    Entry point chính: Build + Upsert toàn bộ chunks vào Qdrant.

    Args:
        chunks:         Danh sách chunks từ chunker.py.
        qdrant_client:  QdrantClient đã kết nối.
        collection:     Tên collection Qdrant.
        batch_size:     Số points mỗi batch upsert.

    Returns:
        Số lượng points đã upsert thành công.
    """
    if not chunks:
        logger.warning("[Indexer] Không có chunks để index.")
        return 0

    points = build_points(chunks, batch_size=int(os.getenv("EMBED_BATCH_SIZE", "32")))
    if not points:
        return 0

    total = 0
    for i in range(0, len(points), batch_size):
        batch = points[i: i + batch_size]
        try:
            qdrant_client.upsert(
                collection_name=collection,
                points=batch,
                wait=True,
            )
            total += len(batch)
            logger.info(
                "[Indexer] Upsert batch %d-%d/%d → collection '%s'",
                i + 1, i + len(batch), len(points), collection,
            )
        except Exception as e:
            logger.error(
                "[Indexer] Lỗi upsert batch %d-%d: %s",
                i + 1, i + len(batch), str(e), exc_info=True,
            )
            # Tiếp tục batch tiếp theo thay vì dừng toàn bộ
            continue

    logger.info(
        "[Indexer] Hoàn thành: %d/%d points vào '%s'.",
        total, len(points), collection,
    )
    return total
