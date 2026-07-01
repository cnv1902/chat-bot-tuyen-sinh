import logging
import uuid
from typing import List, Dict
from qdrant_client import models as qmodels

from core.embedder import embed
from core.vectordb import upsert_points
from db.connection import AsyncSessionLocal
from db.models import UploadedDocument, DocumentChunk
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def approve_and_embed_chunks(doc_id: int, approved_chunks: List[Dict]):
    """
    approved_chunks: List of dicts, e.g. [{"chunk_id": 1, "content": "edited content"}]
    """
    logger.info(f"[QdrantService] Bắt đầu duyệt và embed {len(approved_chunks)} chunks cho document {doc_id}")
    
    try:
        points = []
        async with AsyncSessionLocal() as db:
            doc = await db.get(UploadedDocument, doc_id)
            if not doc:
                raise Exception(f"Không tìm thấy document {doc_id}")

            for chunk_data in approved_chunks:
                chunk_id = chunk_data.get("chunk_id")
                new_content = chunk_data.get("content")
                
                db_chunk = await db.get(DocumentChunk, chunk_id)
                if not db_chunk or db_chunk.document_id != doc_id:
                    continue
                
                # Update DB chunk
                db_chunk.content = new_content
                db_chunk.status = 'approved'
                
                # Create embedding
                vector = embed(new_content)
                
                # Prepare metadata payload
                payload = db_chunk.metadata_payload or {}
                payload['content'] = new_content
                
                # Create Qdrant point
                point = qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        "dense": vector["dense"],
                        "sparse": qmodels.SparseVector(
                            indices=vector["sparse_indices"],
                            values=vector["sparse_values"]
                        )
                    },
                    payload=payload
                )
                points.append(point)
            
            # Đẩy lên Qdrant
            if points:
                upsert_points(points)
            
            # Đánh dấu document hoàn tất
            doc.status = 'success'
            await db.commit()
            
            logger.info(f"[QdrantService] Hoàn tất đẩy {len(points)} vectors lên Qdrant cho doc {doc_id}")
            
    except Exception as e:
        logger.error(f"[QdrantService] Lỗi khi approve/embed: {str(e)}", exc_info=True)
        raise
