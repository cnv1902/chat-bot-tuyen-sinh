"""
llm/__init__.py
===============
Entry point duy nhất cho toàn bộ hệ thống khi cần gọi LLM.

Usage:
    from llm import get_ocr_provider, get_chat_provider

    ocr  = await get_ocr_provider()    # Đọc DB → trả về đúng provider
    chat = await get_chat_provider()   # Đọc DB → trả về đúng provider

    answer   = await chat.complete(messages, system)
    markdown = await ocr.complete_vision(image_path, prompt)

Thiết kế: _load_provider() được gọi mỗi request → không cache →
          thay đổi config qua Admin UI có hiệu lực ngay, không cần restart.
"""
import importlib
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from llm.base import LLMProvider
from db.connection import AsyncSessionLocal
from db.crud import get_slot, get_provider

logger = logging.getLogger(__name__)

# Provider registry — thêm provider mới vào đây
_PROVIDER_MAP: dict[str, str] = {
    "gemini": "llm.gemini.GeminiProvider",
    "openai": "llm.gpt.GPTProvider",
    "groq":   "llm.groq.GroqProvider",
    "vllm":   "llm.vllm.VLLMProvider",
}


async def _load_provider(slot: str) -> LLMProvider:
    """
    Đọc config từ DB và khởi tạo provider tương ứng.

    Được gọi mỗi request — không cache để đảm bảo
    đổi config qua Admin UI có hiệu lực ngay lập tức.

    Raises:
        ValueError: Khi slot hoặc provider chưa được cấu hình trong DB.
    """
    async with AsyncSessionLocal() as db:
        slot_cfg = await get_slot(db, slot)
        if not slot_cfg:
            raise ValueError(
                f"Slot '{slot}' chưa được cấu hình. "
                f"Vào /admin/llm-settings để thiết lập."
            )
        provider_cfg = await get_provider(db, slot_cfg.provider)
        if not provider_cfg:
            raise ValueError(
                f"Provider '{slot_cfg.provider}' chưa có credentials. "
                f"Vào /admin/llm-settings để thêm API key."
            )

    provider_name = slot_cfg.provider
    model_name    = slot_cfg.model_name
    api_key       = provider_cfg.api_key or ""
    endpoint      = provider_cfg.endpoint or ""

    class_path = _PROVIDER_MAP.get(provider_name)
    if not class_path:
        raise ValueError(f"Provider '{provider_name}' không được hỗ trợ.")

    # Dynamic import — tránh load tất cả SDK khi khởi động
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls    = getattr(module, class_name)

    # vLLM cần truyền thêm endpoint
    if provider_name == "vllm":
        return cls(api_key=api_key, model_name=model_name, endpoint=endpoint)
    return cls(api_key=api_key, model_name=model_name)


async def get_ocr_provider() -> LLMProvider:
    """Trả về LLM provider cho slot OCR (phân tích ảnh PDF)."""
    return await _load_provider("ocr")


async def get_chat_provider() -> LLMProvider:
    """Trả về LLM provider cho slot Chat (classify + generate answer)."""
    return await _load_provider("chat")


async def list_available_models(
    provider: str,
    api_key:  str,
    endpoint: str | None = None,
) -> list[str]:
    """
    Gọi API của provider để lấy danh sách model khả dụng.
    Dùng cho Admin UI dropdown — không cache.
    """
    class_path = _PROVIDER_MAP.get(provider)
    if not class_path:
        return []
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls    = getattr(module, class_name)
    return await cls.list_models(api_key=api_key, endpoint=endpoint)

async def get_langchain_chat_model():
    """
    Trả về instance BaseChatModel của LangChain dựa trên config DB.
    Được dùng cho AgentExecutor.
    """
    async with AsyncSessionLocal() as db:
        from db.crud import get_slot, get_provider
        slot_cfg = await get_slot(db, "chat")
        if not slot_cfg:
            raise ValueError("Slot 'chat' chưa được cấu hình.")
        provider_cfg = await get_provider(db, slot_cfg.provider)
        if not provider_cfg:
            raise ValueError("Provider chưa có cấu hình API.")
            
    provider_name = slot_cfg.provider
    model_name    = slot_cfg.model_name
    api_key       = provider_cfg.api_key or ""
    
    if provider_name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0)
    elif provider_name == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_name, openai_api_key=api_key, temperature=0)
    elif provider_name == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model_name, groq_api_key=api_key, temperature=0)
    else:
        raise ValueError(f"LangChain integration cho provider '{provider_name}' chưa được implement.")
