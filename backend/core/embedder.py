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
from FlagEmbedding import BGEM3FlagModel
from huggingface_hub import login

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Singleton State (Module-level — tồn tại suốt vòng đời process)
# ---------------------------------------------------------------------------

_model_instance: Optional[BGEM3FlagModel] = None
_model_lock = threading.Lock()          # Đảm bảo thread-safe khi init lần đầu
_model_name: Optional[str] = None      # Cache tên model để detect config thay đổi


# ---------------------------------------------------------------------------
# Singleton Loader
# ---------------------------------------------------------------------------

def _get_model() -> BGEM3FlagModel:
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
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                logger.info("[Embedder] Tìm thấy HF_TOKEN, tiến hành xác thực HuggingFace để tăng tốc độ tải...")
                login(token=hf_token, add_to_git_credential=False)
            
            # device="cpu" tường minh — tránh lỗi trên server không có CUDA
            # Có thể đổi thành "cuda" nếu server có GPU
            device = os.getenv("EMBED_DEVICE", "cpu").strip()

            _model_instance = BGEM3FlagModel(
                target_model,
                use_fp16=True if device != "cpu" else False, # fp16 chỉ cho GPU
                device=device,
            )
            _model_name = target_model

            # BGEM3FlagModel có config ẩn bên trong model.model
            embed_dim = 1024 # BGE-M3 default dimension
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

def embed(text: str) -> dict:
    """
    Encode một đoạn văn bản đơn lẻ thành hybrid vector embedding (dense + sparse).

    Returns:
        Dict chứa `dense`, `sparse_indices`, `sparse_values`.
    """
    if not text or not text.strip():
        raise ValueError("[Embedder] Không thể encode chuỗi văn bản rỗng.")

    try:
        model = _get_model()
        out = model.encode(
            [text.strip()],
            max_length=512,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        
        dense_vec = out['dense_vecs'][0].tolist()
        lexical_weights = out['lexical_weights'][0]
        
        # Lấy keys và values dưới dạng chuỗi int và float cho sparse vector
        sparse_indices = [int(k) for k in lexical_weights.keys()]
        sparse_values = [float(v) for v in lexical_weights.values()]
        
        return {
            "dense": dense_vec,
            "sparse_indices": sparse_indices,
            "sparse_values": sparse_values
        }

    except ValueError:
        raise
    except Exception as e:
        logger.error("[Embedder] Lỗi khi encode text: %s", str(e), exc_info=True)
        raise RuntimeError(f"Lỗi embedding: {e}") from e


def embed_batch(texts: list[str], batch_size: int = 0) -> list[dict]:
    """
    Encode một danh sách văn bản thành batch hybrid vector embeddings.

    Dùng cho: Indexing Pipeline (xử lý hàng trăm chunks cùng lúc).
    Tối ưu throughput thông qua batched encoding.

    Args:
        texts:      Danh sách văn bản cần encode. Bỏ qua chuỗi rỗng tự động.
        batch_size: Số lượng texts xử lý mỗi batch. Nếu = 0, đọc từ biến
                    môi trường EMBED_BATCH_SIZE (mặc định 32).

    Returns:
        Danh sách các dictionary chứa `dense`, `sparse_indices`, `sparse_values`.
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

        out = model.encode(
            valid_texts,
            batch_size=batch_size,
            max_length=512, # Giới hạn độ dài để tăng tốc độ CPU Inference
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )

        dense_vecs = out['dense_vecs']
        lexical_weights_list = out['lexical_weights']
        
        results = []
        for i in range(len(valid_texts)):
            sparse_indices = [int(k) for k in lexical_weights_list[i].keys()]
            sparse_values = [float(v) for v in lexical_weights_list[i].values()]
            results.append({
                "dense": dense_vecs[i].tolist(),
                "sparse_indices": sparse_indices,
                "sparse_values": sparse_values
            })

        logger.info("[Embedder] Batch encode hoàn thành: %d hybrid vectors.", len(results))
        return results

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
    return 1024


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
            "[Embedder] Warmup thành công | Vector dim: %d | Sparse Tokens: %d",
            len(test_vector["dense"]),
            len(test_vector["sparse_indices"])
        )
    except Exception as e:
        logger.error("[Embedder] Warmup thất bại: %s", str(e), exc_info=True)
        # Không raise — để app vẫn khởi động được, lỗi sẽ xuất hiện khi dùng thực
