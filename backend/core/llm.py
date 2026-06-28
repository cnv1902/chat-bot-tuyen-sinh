"""
core/llm.py
===========
DEPRECATED: File này được giữ lại CHỈ cho backward compatibility.

Code mới PHẢI import trực tiếp từ llm/ package:
    from llm import get_chat_provider, get_ocr_provider

Các hàm ở đây là thin wrapper gọi vào llm/ — sẽ bị remove trong phiên bản tiếp theo.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


def chat_complete(
    messages:    list[dict],
    system:      str,
    max_tokens:  int   = 1024,
    temperature: float = 0.0,
) -> str:
    """
    DEPRECATED — Dùng ``await (await get_chat_provider()).complete(...)`` thay thế.
    Wrapper sync cho backward compatibility với code cũ chưa được migrate.
    """
    logger.debug(
        "[core.llm] chat_complete() gọi qua backward-compat wrapper → llm package"
    )

    async def _run():
        from llm import get_chat_provider
        provider = await get_chat_provider()
        return await provider.complete(messages, system, max_tokens, temperature)

    return asyncio.run(_run())


def chat_complete_json(
    messages:   list[dict],
    system:     str,
    max_tokens: int = 800,
) -> str:
    """
    DEPRECATED — Dùng ``await (await get_chat_provider()).complete_json(...)`` thay thế.
    Wrapper sync cho backward compatibility với code cũ chưa được migrate.
    """
    logger.debug(
        "[core.llm] chat_complete_json() gọi qua backward-compat wrapper → llm package"
    )

    async def _run():
        from llm import get_chat_provider
        provider = await get_chat_provider()
        return await provider.complete_json(messages, system, max_tokens)

    return asyncio.run(_run())
