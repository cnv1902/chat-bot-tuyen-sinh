"""
core/embedder.py
================
SentenceTransformer Wrapper — Singleton Pattern với Thread-Safe Loading.

Thiết kế:
- BAAI/bge-m3 là model đa ngôn ngữ ~570MB, việc load vào RAM
  tốn ~3-8 giây. Dùng Singleton để chỉ load DUY NHẤT MỘT LẦN.
- Thread-safe qua threading.Lock() — đảm bảo an toàn khi FastAPI
  xử lý nhiều request đồng thời trong môi trường production.
- Hỗ trợ batch encoding để tối ưu throughput khi indexing pipeline
  xử lý hàng trăm chunks cùng lúc.
- Normalize_embeddings=True bắt buộc để vector tương thích
  với metric Cosine Similarity trong Qdrant.
"""

import logging
import os
import threading
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Singleton State (Module-level — tồn tại suốt vòng đời process)
# ---------------------------------------------------------------------------

_model_instance: Optional[SentenceTransformer] = None
_model_lock = threading.Lock()          # Đảm bảo thread-safe khi init lần đầu
_model_name: Optional[str] = None      # Cache tên model để detect config thay đổi


# ---------------------------------------------------------------------------
# Singleton Loader
# ---------------------------------------------------------------------------

def _get_model() -> SentenceTransformer:
    """
    Trả về instance SentenceTransformer duy nhất.
    Load model từ disk/HuggingFace cache nếu chưa khởi tạo.

    Thread-safe: dùng double-checked locking pattern để tránh race condition
    trong trường hợp nhiều requests đến đồng thời ngay khi server khởi động.

    Returns:
        SentenceTransformer instance đã sẵn sàng encode.

    Raises:
        RuntimeError: Nếu không thể load model (lỗi mạng, thiếu RAM...).
    """
    global _model_instance, _model_name

    target_model = os.getenv("EMBED_MODEL", "BAAI/bge-m3").strip()

    # --- Fast path: model đã tồn tại và chưa thay đổi ---
    if _model_instance is not None and _model_name == target_model:
        return _model_instance

    # --- Slow path: acquire lock và khởi tạo ---
    with _model_lock:
        # Double-check sau khi acquire lock (tránh race condition)
        if _model_instance is not None and _model_name == target_model:
            return _model_instance

        logger.info(
            "[Embedder] Đang tải model '%s' vào RAM... "
            "(Quá trình này chỉ diễn ra một lần)",
            target_model,
        )

        try:
            # device="cpu" tường minh — tránh lỗi trên server không có CUDA
            # Có thể đổi thành "cuda" nếu server có GPU
            device = os.getenv("EMBED_DEVICE", "cpu").strip()

            _model_instance = SentenceTransformer(
                model_name_or_path=target_model,
                device=device,
            )
            _model_name = target_model

            # Log thông tin model để dễ debug
            embed_dim = _model_instance.get_sentence_embedding_dimension()
            logger.info(
                "[Embedder] Model '%s' đã sẵn sàng | Device: %s | Dim: %d",
                target_model,
                device,
                embed_dim,
            )

        except Exception as e:
            logger.critical(
                "[Embedder] KHÔNG THỂ tải model '%s': %s",
                target_model,
                str(e),
                exc_info=True,
            )
            raise RuntimeError(
                f"Không thể khởi tạo embedding model '{target_model}'. "
                f"Lỗi gốc: {e}"
            ) from e

    return _model_instance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed(text: str) -> list[float]:
    """
    Encode một đoạn văn bản đơn lẻ thành vector embedding.

    Dùng cho: Encoding câu hỏi của người dùng trong luồng Real-time Inference.
    Ưu tiên tốc độ (single query, không cần batch).

    Args:
        text: Chuỗi văn bản cần encode. Sẽ bị truncate tự động
              nếu vượt quá max_length của model (8192 tokens với bge-m3).

    Returns:
        Danh sách float biểu diễn vector embedding chiều 1024.
        Đã được normalize L2 để tương thích với Cosine Similarity.

    Raises:
        RuntimeError: Nếu model chưa được load thành công.
        ValueError: Nếu text là chuỗi rỗng.
    """
    if not text or not text.strip():
        raise ValueError("[Embedder] Không thể encode chuỗi văn bản rỗng.")

    try:
        model = _get_model()
        vector: np.ndarray = model.encode(
            text.strip(),
            normalize_embeddings=True,   # Bắt buộc để dùng Cosine Similarity
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vector.tolist()

    except ValueError:
        raise
    except Exception as e:
        logger.error("[Embedder] Lỗi khi encode text: %s", str(e), exc_info=True)
        raise RuntimeError(f"Lỗi embedding: {e}") from e


def embed_batch(texts: list[str], batch_size: int = 0) -> list[list[float]]:
    """
    Encode một danh sách văn bản thành batch vector embeddings.

    Dùng cho: Indexing Pipeline (xử lý hàng trăm chunks cùng lúc).
    Tối ưu throughput thông qua batched encoding của SentenceTransformer.

    Args:
        texts:      Danh sách văn bản cần encode. Bỏ qua chuỗi rỗng tự động.
        batch_size: Số lượng texts xử lý mỗi batch. Nếu = 0, đọc từ biến
                    môi trường EMBED_BATCH_SIZE (mặc định 32).

    Returns:
        Danh sách các vector embedding tương ứng (đã normalize L2).
        Số lượng phần tử = số lượng texts hợp lệ (sau khi lọc rỗng).

    Raises:
        RuntimeError: Nếu model không thể load.
        ValueError: Nếu danh sách texts rỗng hoàn toàn.
    """
    # Lọc bỏ chuỗi rỗng, giữ nguyên thứ tự
    valid_texts = [t.strip() for t in texts if t and t.strip()]

    if not valid_texts:
        raise ValueError("[Embedder] Danh sách texts rỗng sau khi lọc.")

    # Đọc batch_size từ env nếu không truyền vào
    if batch_size <= 0:
        batch_size = int(os.getenv("EMBED_BATCH_SIZE", "32"))

    try:
        model = _get_model()
        logger.info(
            "[Embedder] Bắt đầu batch encode %d texts (batch_size=%d)...",
            len(valid_texts),
            batch_size,
        )

        vectors: np.ndarray = model.encode(
            valid_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(valid_texts) > 50,  # Chỉ show progress bar khi nhiều
            convert_to_numpy=True,
        )

        logger.info("[Embedder] Batch encode hoàn thành: %d vectors.", len(vectors))
        return vectors.tolist()

    except ValueError:
        raise
    except Exception as e:
        logger.error("[Embedder] Lỗi batch encoding: %s", str(e), exc_info=True)
        raise RuntimeError(f"Lỗi batch embedding: {e}") from e


def get_embedding_dimension() -> int:
    """
    Trả về số chiều vector của model hiện tại.

    Dùng để tự động cấu hình Qdrant collection dimension
    thay vì hardcode 1024 ở nhiều nơi.

    Returns:
        Số chiều embedding (1024 với BAAI/bge-m3).
    """
    model = _get_model()
    dim = model.get_sentence_embedding_dimension()
    return dim if dim is not None else int(os.getenv("EMBED_DIMENSION", "1024"))


def warmup() -> None:
    """
    Khởi động sẵn model khi FastAPI app startup để request đầu tiên
    không bị chậm do phải load model.

    Gọi hàm này trong FastAPI startup event:
        @app.on_event("startup")
        async def startup_event():
            warmup()
    """
    logger.info("[Embedder] Thực hiện warmup — pre-loading embedding model...")
    try:
        _get_model()
        # Encode một câu thử để chắc chắn model hoạt động đúng
        test_vector = embed("Trường Đại học Vinh tuyển sinh năm 2026")
        logger.info(
            "[Embedder] Warmup thành công | Vector dim: %d",
            len(test_vector),
        )
    except Exception as e:
        logger.error("[Embedder] Warmup thất bại: %s", str(e), exc_info=True)
        # Không raise — để app vẫn khởi động được, lỗi sẽ xuất hiện khi dùng thực
