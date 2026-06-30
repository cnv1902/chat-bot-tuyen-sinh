import logging
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db.connection import get_db
from db.models import UploadedDocument, DocumentChunk, DocTypeEnum
from core.parser_service import process_document
from core.qdrant_service import approve_and_embed_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = _BACKEND_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class ChunkApproval(BaseModel):
    chunk_id: int
    content: str

class BulkDeleteChunks(BaseModel):
    chunk_ids: List[int]

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    year: Optional[int] = Form(None),
    doc_type: DocTypeEnum = Form(DocTypeEnum.KHAC),
    db: AsyncSession = Depends(get_db)
):
    try:
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        doc = UploadedDocument(
            filename=file.filename,
            year=year,
            doc_type=doc_type.value,
            status="processing"
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        # Dispatch background task
        background_tasks.add_task(process_document, doc.id, str(file_path), year, doc_type.value)
        
        return {"message": "Tài liệu đang được xử lý", "document_id": doc.id}
    except Exception as e:
        logger.error(f"[Upload] Lỗi khi upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Không thể upload file")

@router.get("")
async def get_documents(db: AsyncSession = Depends(get_db)):
    stmt = select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return docs

import os
from core.vectordb import delete_points_by_document_id

@router.delete("/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
        
    # Xóa file vật lý
    file_path = os.path.join(UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Không thể xóa file vật lý {file_path}: {e}")
            
    # Xóa vectors trong Qdrant
    delete_points_by_document_id(doc_id)
    
    # Xóa document trong Postgres (tự động cascade xóa document_chunks)
    await db.delete(doc)
    await db.commit()
    return {"message": "Đã xóa tài liệu và các chunk liên quan"}

@router.get("/{doc_id}/chunks")
async def get_document_chunks(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
        
    stmt = select(DocumentChunk).where(
        DocumentChunk.document_id == doc_id,
        DocumentChunk.status == 'pending'
    ).order_by(DocumentChunk.id.asc())
    
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    return chunks

@router.post("/{doc_id}/approve-chunks")
async def approve_chunks(
    doc_id: int,
    payload: List[ChunkApproval],
    db: AsyncSession = Depends(get_db)
):
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
        
    if doc.status != 'pending_review':
        raise HTTPException(status_code=400, detail="Tài liệu không ở trạng thái chờ duyệt")
        
    approved_list = [{"chunk_id": item.chunk_id, "content": item.content} for item in payload]
    
    try:
        # Call Qdrant service to embed and upsert
        await approve_and_embed_chunks(doc_id, approved_list)
        return {"message": "Đã duyệt và lưu các chunk thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chunks/delete")
async def delete_chunks(
    payload: BulkDeleteChunks,
    db: AsyncSession = Depends(get_db)
):
    if not payload.chunk_ids:
        return {"message": "Không có chunk nào được chọn"}
        
    # Delete chunks from DB
    from sqlalchemy import delete
    stmt = delete(DocumentChunk).where(DocumentChunk.id.in_(payload.chunk_ids))
    await db.execute(stmt)
    await db.commit()
    
    return {"message": f"Đã xóa {len(payload.chunk_ids)} chunk"}
