"""
db/crud.py
==========
CRUD operations cho LLM configuration.
Tất cả hàm đều async, nhận AsyncSession làm tham số.
Caller chịu trách nhiệm quản lý session (dùng Depends(get_db) trong router).
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from db.models import LLMProvider, LLMSlot

logger = logging.getLogger(__name__)


# ── LLMProvider CRUD ──────────────────────────────────────────────────────────

async def get_all_providers(db: AsyncSession) -> list[LLMProvider]:
    """Lấy tất cả providers trong DB."""
    result = await db.execute(select(LLMProvider).order_by(LLMProvider.provider))
    return list(result.scalars().all())


async def get_provider(db: AsyncSession, provider: str) -> LLMProvider | None:
    """Lấy provider theo tên. Trả về None nếu chưa tồn tại."""
    result = await db.execute(
        select(LLMProvider).where(LLMProvider.provider == provider)
    )
    return result.scalar_one_or_none()


async def upsert_provider(
    db: AsyncSession,
    provider: str,
    api_key:  str | None = None,
    endpoint: str | None = None,
    is_active: bool = True,
) -> LLMProvider:
    """
    Tạo mới hoặc cập nhật provider credentials.
    Chỉ cập nhật field nào được truyền vào (api_key=None nghĩa là không thay đổi).
    """
    existing = await get_provider(db, provider)
    if existing:
        if api_key is not None:
            existing.api_key = api_key
        if endpoint is not None:
            existing.endpoint = endpoint
        existing.is_active = is_active
        obj = existing
    else:
        obj = LLMProvider(
            provider=provider,
            api_key=api_key,
            endpoint=endpoint,
            is_active=is_active,
        )
        db.add(obj)

    await db.commit()
    await db.refresh(obj)
    logger.info("[DB] Upsert provider '%s' → is_active=%s", provider, is_active)
    return obj


# ── LLMSlot CRUD ──────────────────────────────────────────────────────────────

async def get_all_slots(db: AsyncSession) -> list[LLMSlot]:
    """Lấy tất cả slot configs."""
    result = await db.execute(select(LLMSlot).order_by(LLMSlot.slot))
    return list(result.scalars().all())


async def get_slot(db: AsyncSession, slot: str) -> LLMSlot | None:
    """Lấy slot config theo tên. Trả về None nếu chưa được cấu hình."""
    result = await db.execute(
        select(LLMSlot).where(LLMSlot.slot == slot)
    )
    return result.scalar_one_or_none()


async def upsert_slot(
    db: AsyncSession,
    slot: str,
    provider: str,
    model_name: str,
) -> LLMSlot:
    """
    Tạo mới hoặc cập nhật slot config.
    Thay đổi có hiệu lực ngay với request tiếp theo (không cần restart).
    """
    existing = await get_slot(db, slot)
    if existing:
        existing.provider   = provider
        existing.model_name = model_name
        obj = existing
    else:
        obj = LLMSlot(slot=slot, provider=provider, model_name=model_name)
        db.add(obj)

    await db.commit()
    await db.refresh(obj)
    logger.info("[DB] Upsert slot '%s' → %s/%s", slot, provider, model_name)
    return obj


# ── UploadedDocument CRUD ─────────────────────────────────────────────────────

async def create_uploaded_document(
    db: AsyncSession,
    filename: str,
    year: int,
) -> "UploadedDocument":
    """
    Tạo bản ghi mới với trạng thái 'processing'.
    Gọi ngay sau khi file được lưu vào disk, trước khi background task bắt đầu.
    Trả về object với id để background task dùng khi cập nhật trạng thái.
    """
    from db.models import UploadedDocument
    doc = UploadedDocument(filename=filename, year=year, status="processing")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    logger.info("[DB] Created uploaded_document id=%d | file=%r | year=%d", doc.id, filename, year)
    return doc


async def update_uploaded_document_status(
    db: AsyncSession,
    doc_id: int,
    status: str,
    message: str | None = None,
) -> None:
    """
    Cập nhật trạng thái sau khi background task hoàn tất (thành công hoặc lỗi).
    status: "success" | "failed"
    message: tóm tắt kết quả hoặc mô tả lỗi.
    """
    from db.models import UploadedDocument
    from datetime import datetime, timezone
    result = await db.execute(
        select(UploadedDocument).where(UploadedDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        logger.warning("[DB] update_uploaded_document_status: id=%d không tồn tại", doc_id)
        return
    doc.status = status
    doc.message = message
    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("[DB] Updated uploaded_document id=%d → status=%r", doc_id, status)


async def get_all_uploaded_documents(
    db: AsyncSession,
    limit: int = 50,
) -> list["UploadedDocument"]:
    """
    Lấy danh sách tài liệu đã upload, mới nhất trước.
    Dùng cho GET /api/upload/documents phục vụ Admin UI polling.
    """
    from db.models import UploadedDocument
    from sqlalchemy import desc
    result = await db.execute(
        select(UploadedDocument)
        .order_by(desc(UploadedDocument.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_uploaded_document(
    db: AsyncSession,
    doc_id: int,
) -> "UploadedDocument | None":
    """
    Lấy thông tin 1 tài liệu theo ID.
    Trả về None nếu không tìm thấy.
    """
    from db.models import UploadedDocument
    result = await db.execute(
        select(UploadedDocument).where(UploadedDocument.id == doc_id)
    )
    return result.scalar_one_or_none()


async def delete_uploaded_document(
    db: AsyncSession,
    doc_id: int,
) -> bool:
    """
    Xóa bản ghi tài liệu khỏi bảng uploaded_documents theo ID.
    Trả về True nếu xóa thành công, False nếu không tìm thấy bản ghi.
    """
    from db.models import UploadedDocument
    result = await db.execute(
        delete(UploadedDocument).where(UploadedDocument.id == doc_id)
    )
    await db.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info("[DB] Đã xóa uploaded_document id=%d", doc_id)
    else:
        logger.warning("[DB] delete_uploaded_document: id=%d không tồn tại", doc_id)
    return deleted
