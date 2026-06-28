"""
api/routers/upload.py
=====================
Endpoint cho phép upload tài liệu tuyển sinh.
Lưu file tạm và dùng BackgroundTasks để xử lý ngầm.

Mỗi file upload được theo dõi trong bảng uploaded_documents:
  - Trạng thái "processing" được tạo ngay khi nhận file.
  - Background task cập nhật thành "success" hoặc "failed" khi hoàn tất.
  - GET /api/upload/documents trả về danh sách để Admin UI polling mỗi 5 giây.
"""

import logging
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db, AsyncSessionLocal
from db.crud import (
    create_uploaded_document,
    update_uploaded_document_status,
    get_all_uploaded_documents,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Upload"])

# BUG FIX: Path tương đối sẽ resolve từ CWD khi uvicorn khởi động.
# Dùng Path(__file__) để tính đường dẫn tuyệt đối từ vị trí file này.
# upload.py nằm ở: backend/api/routers/upload.py
# → backend/ nằm 3 cấp lên → backend/data/uploads
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = _BACKEND_ROOT / "data" / "uploads"
# Tạo thư mục nếu chưa tồn tại (idempotent)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def process_file_background(
    doc_id: int,
    file_path: str,
    year: int,
):
    """
    Hàm xử lý ngầm tài liệu.

    doc_id: ID bản ghi trong uploaded_documents để cập nhật kết quả sau khi xong.
    doc_type được Gemini Vision tự động phân loại từ nội dung từng trang PDF.
    Fallback 'khac' chỉ dùng khi Gemini Vision thất bại hoàn toàn.
    """
    fallback_doc_type = "khac"  # Gemini Vision sẽ ghi đè trên hầu hết các trang
    logger.info("========== BACKGROUND TASK ==========")
    logger.info("[Background] Bắt đầu xử lý file: %s", file_path)
    logger.info(
        "[Background] Year: %d | doc_type fallback: %s (Gemini Vision sẽ tự xác định)",
        year, fallback_doc_type,
    )

    import asyncio
    from indexing.run_pipeline import process_pdf
    from indexing.vision_extractor import set_main_loop
    from qdrant_client import QdrantClient
    import os

    start_time = time.time()
    try:
        # Khởi tạo Qdrant Client theo config của hệ thống
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        collection_name = os.getenv("QDRANT_COLLECTION", "tuyen_sinh_dhv")

        logger.info(
            "[Background] Đang kết nối Qdrant tại %s:%d (Collection: %s)",
            qdrant_host, qdrant_port, collection_name,
        )
        qdrant = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=30)

        logger.info("[Background] Bắt đầu chạy pipeline OCR & Chunking (tiến trình này có thể mất vài phút)...")

        # Inject event loop hiện tại vào vision_extractor TRƯỚC khi chuyển sang thread.
        main_loop = asyncio.get_running_loop()
        set_main_loop(main_loop)

        # Chạy pipeline CPU-heavy trong thread pool để không block event loop.
        result = await asyncio.to_thread(
            process_pdf,
            pdf_path=file_path,
            qdrant=qdrant,
            collection=collection_name,
            fallback_year=year,
            fallback_doc_type=fallback_doc_type,
            tmp_dir=str(_BACKEND_ROOT / "tmp_images"),
        )

        duration = time.time() - start_time
        pages   = result["pages"]
        chunks  = result["chunks"]
        indexed = result["indexed"]

        logger.info("✅ HOÀN TẤT XỮ LÝ FILE: %s", file_path)
        logger.info("[Background] Thống kê: %d trang | %d chunks tạo ra | %d chunks đã index", pages, chunks, indexed)
        if result["needs_review"]:
            logger.warning(
                "[Background] ⚠️ Có %d trang cần rà soát lại dữ liệu.",
                len(result["needs_review"]),
            )
        logger.info("[Background] Thời gian thực thi: %.2f giây", duration)

        # Cập nhật trạng thái thành công vào DB
        # Dùng AsyncSessionLocal trực tiếp (không dùng get_db() — đó là generator cho Depends)
        success_msg = f"{pages} trang | {chunks} chunks tạo ra | {indexed} chunks đã index | {duration:.1f}s"
        async with AsyncSessionLocal() as db:
            await update_uploaded_document_status(
                db, doc_id=doc_id, status="success", message=success_msg,
            )

    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        logger.error(
            "[Background] ❌ LỖI TRONG QUÁ TRÌNH XỮ LÝ FILE %s: %s",
            file_path, error_msg, exc_info=True,
        )
        # Cập nhật trạng thái thất bại vào DB
        try:
            async with AsyncSessionLocal() as db:
                await update_uploaded_document_status(
                    db, doc_id=doc_id, status="failed", message=error_msg[:500],
                )
        except Exception as db_err:
            logger.error("[Background] Không thể cập nhật trạng thái lỗi vào DB: %s", db_err)
    finally:
        logger.info("=====================================")


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload tài liệu tuyển sinh (Xử lý ngầm)",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    year: int = Form(default=2026),
    db: AsyncSession = Depends(get_db),
):
    """
    Nhận file (PDF, DOCX) và năm tuyển sinh từ admin, lưu tạm và đẩy vào background task.
    Tạo bản ghi trạng thái trong DB ngay lập tức để Admin UI theo dõi tiến độ.
    """
    # 1. Validate định dạng file
    allowed_extensions = {".pdf", ".docx"}
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng không hợp lệ. Chỉ hỗ trợ {', '.join(allowed_extensions)}"
        )

    # 2. Lưu file vào ổ cứng
    file_path = UPLOAD_DIR / filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error("Lỗi khi lưu file %s: %s", filename, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể lưu file trên server."
        )

    # 3. Tạo bản ghi trạng thái trong DB (status = "processing")
    doc = await create_uploaded_document(db, filename=filename, year=year)
    doc_id = doc.id
    logger.info("[Upload] File %r đã lưu. DB doc_id=%d. Đẩy vào background task.", filename, doc_id)

    # 4. Đẩy vào BackgroundTasks
    background_tasks.add_task(
        process_file_background,
        doc_id=doc_id,
        file_path=str(file_path.absolute()),
        year=year,
    )

    # 5. Trả về response ngay lập tức
    return {
        "message": f"File '{filename}' đã được nhận và đang được xử lý ngầm.",
        "doc_id": doc_id,
        "status": "processing",
    }


@router.get(
    "/upload/documents",
    summary="Danh sách tài liệu đã nạp và trạng thái xử lý",
)
async def list_uploaded_documents(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Trả về danh sách tài liệu tuyển sinh đã được upload kèm trạng thái xử lý.
    Dùng cho Admin UI polling mỗi 5 giây để theo dõi tiến độ background task.

    Trạng thái:
        processing → Đang xử lý (OCR + chunk + index)
        success    → Hoàn tất, đã index vào Qdrant
        failed     → Xử lý thất bại (xem message để biết nguyên nhân)
    """
    docs = await get_all_uploaded_documents(db, limit=limit)
    return [
        {
            "id":         doc.id,
            "filename":   doc.filename,
            "year":       doc.year,
            "status":     doc.status,
            "message":    doc.message,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
        for doc in docs
    ]
