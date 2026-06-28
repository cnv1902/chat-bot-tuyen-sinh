"""
api/routers/admin.py
====================
REST API cho trang quản trị LLM.
Prefix: /admin

Endpoints:
  GET  /admin/providers           → Lấy tất cả provider config (ẩn API key)
  POST /admin/providers           → Tạo/cập nhật provider credentials
  GET  /admin/slots               → Lấy config 2 slots (ocr/chat)
  POST /admin/slots               → Cập nhật slot config
  GET  /admin/models/{provider}   → Lấy danh sách model khả dụng từ provider API
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.crud import (
    get_all_providers,
    get_provider,
    upsert_provider,
    get_all_slots,
    upsert_slot,
)
from llm import list_available_models

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin - LLM Management"])

VALID_PROVIDERS = {"openai", "gemini", "groq", "vllm"}
VALID_SLOTS     = {"ocr", "chat"}


# ── Pydantic Request/Response Schemas ──────────────────────────────────────

class ProviderUpdate(BaseModel):
    provider:  str
    api_key:   str | None = None
    endpoint:  str | None = None
    is_active: bool = True


class SlotUpdate(BaseModel):
    slot:       str  # "ocr" hoặc "chat"
    provider:   str
    model_name: str


# ── Provider endpoints ─────────────────────────────────────────────────────

@router.get("/providers", summary="Lấy danh sách providers")
async def get_providers(db: AsyncSession = Depends(get_db)):
    """
    Trả về danh sách tất cả providers đã cấu hình.
    API key được ẩn (chỉ cho biết đã cấu hình hay chưa).
    """
    providers = await get_all_providers(db)
    return [
        {
            "provider":   p.provider,
            "has_key":    bool(p.api_key),
            "endpoint":   p.endpoint,
            "is_active":  p.is_active,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in providers
    ]


@router.post("/providers", summary="Tạo hoặc cập nhật provider")
async def update_provider(
    body: ProviderUpdate,
    db:   AsyncSession = Depends(get_db),
):
    """
    Tạo mới hoặc cập nhật credentials của một provider.
    Nếu truyền api_key=None, giữ nguyên key cũ trong DB.
    """
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Provider không hợp lệ: '{body.provider}'. Hợp lệ: {VALID_PROVIDERS}",
        )

    obj = await upsert_provider(
        db,
        provider=body.provider,
        api_key=body.api_key,
        endpoint=body.endpoint,
        is_active=body.is_active,
    )
    return {"success": True, "provider": obj.provider, "is_active": obj.is_active}


# ── Slot endpoints ─────────────────────────────────────────────────────────

@router.get("/slots", summary="Lấy cấu hình slots OCR/Chat")
async def get_slots(db: AsyncSession = Depends(get_db)):
    """
    Trả về cấu hình hiện tại của 2 slot:
    - ocr:  Provider/model dùng cho phân tích PDF
    - chat: Provider/model dùng cho chatbot
    """
    slots = await get_all_slots(db)
    return [
        {
            "slot":       s.slot,
            "provider":   s.provider,
            "model_name": s.model_name,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in slots
    ]


@router.post("/slots", summary="Cập nhật cấu hình slot")
async def update_slot(
    body: SlotUpdate,
    db:   AsyncSession = Depends(get_db),
):
    """
    Cập nhật provider/model cho một slot.
    Thay đổi có hiệu lực ngay với request tiếp theo — không cần restart.
    """
    if body.slot not in VALID_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Slot không hợp lệ: '{body.slot}'. Hợp lệ: {VALID_SLOTS}",
        )
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Provider không hợp lệ: '{body.provider}'. Hợp lệ: {VALID_PROVIDERS}",
        )

    # Kiểm tra provider đã có credentials chưa
    provider_cfg = await get_provider(db, body.provider)
    if not provider_cfg:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{body.provider}' chưa có credentials. Thêm API key trước.",
        )

    obj = await upsert_slot(
        db,
        slot=body.slot,
        provider=body.provider,
        model_name=body.model_name,
    )
    logger.info("[Admin] Slot '%s' → %s/%s", obj.slot, obj.provider, obj.model_name)
    return {
        "success":    True,
        "slot":       obj.slot,
        "provider":   obj.provider,
        "model_name": obj.model_name,
    }


# ── List models endpoint ───────────────────────────────────────────────────

@router.get("/models/{provider}", summary="Lấy danh sách model của provider")
async def get_models(
    provider: str,
    api_key:  str | None = None,
    endpoint: str | None = None,
    db:       AsyncSession = Depends(get_db),
):
    """
    Gọi API của provider để lấy danh sách model khả dụng.
    Dùng cho Admin UI dropdown — không cache.

    Nếu không truyền api_key, đọc từ DB.
    vLLM luôn trả về [] — admin nhập tay model name.
    """
    if provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Provider không hợp lệ: '{provider}'",
        )

    # Nếu không truyền api_key, đọc từ DB
    if not api_key:
        p = await get_provider(db, provider)
        if p:
            api_key  = p.api_key or ""
            endpoint = endpoint or p.endpoint

    models = await list_available_models(
        provider=provider,
        api_key=api_key or "",
        endpoint=endpoint,
    )
    return {"provider": provider, "models": models}
