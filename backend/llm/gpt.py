"""
llm/gpt.py
==========
OpenAI GPT provider — implement LLMProvider interface.
Dùng openai Python SDK (async native).
Requires: openai>=1.30.0
"""
import base64
import logging

from llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GPTProvider(LLMProvider):

    def __init__(self, api_key: str, model_name: str):
        self.model_name = model_name
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=api_key)
            logger.info("[GPT] Khởi tạo | model=%s", model_name)
        except ImportError:
            raise ImportError(
                "openai package chưa được cài. Chạy: pip install openai>=1.30.0"
            )

    async def complete(
        self,
        messages:    list[dict],
        system:      str,
        max_tokens:  int   = 2048,
        temperature: float = 0.0,
        top_p:       float | None = None,
    ) -> str:
        try:
            full_messages = [{"role": "system", "content": system}] + messages
            kwargs: dict = dict(
                model=self.model_name,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if top_p is not None:
                kwargs["top_p"] = top_p
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or self._fallback()
        except Exception as e:
            logger.error("[GPT/complete] Lỗi: %s", e)
            return self._fallback()

    async def complete_json(
        self,
        messages:   list[dict],
        system:     str,
        max_tokens: int = 800,
    ) -> str:
        try:
            full_messages = [{"role": "system", "content": system}] + messages
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or "{}"
        except Exception as e:
            logger.error("[GPT/JSON] Lỗi: %s", e)
            return "{}"

    async def complete_vision(
        self,
        image_path: str,
        prompt:     str,
        max_tokens: int = 4096,
    ) -> str:
        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }},
                    ],
                }],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("[GPT/Vision] Lỗi: %s", e)
            return ""

    @classmethod
    async def list_models(
        cls,
        api_key:  str,
        endpoint: str | None = None,
    ) -> list[str]:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            models = await client.models.list()
            # Chỉ lấy GPT models có khả năng chat
            return sorted([
                m.id for m in models.data
                if "gpt" in m.id.lower()
            ])
        except Exception as e:
            logger.error("[GPT] list_models error: %s", e)
            return []

    @staticmethod
    def _fallback() -> str:
        return (
            "Hệ thống tạm thời không thể xử lý yêu cầu. "
            "Vui lòng thử lại sau."
        )
