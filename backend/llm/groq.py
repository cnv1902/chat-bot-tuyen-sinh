"""
llm/groq.py
===========
Groq provider — implement LLMProvider interface.
Groq dùng OpenAI-compatible API nên cấu trúc tương tự gpt.py.
Requires: groq>=0.9.0

QUAN TRỌNG: Groq KHÔNG hỗ trợ vision — complete_vision luôn trả về ''.
            Đừng cấu hình slot "ocr" sang Groq provider.

GHI CHÚ VỀ QWEN3 (THINKING MODEL):
    Qwen3-32b trên Groq là reasoning model — mặc định xuất <think>...</think>
    trước câu trả lời. Groq KHÔNG hỗ trợ tắt thinking qua extra_body (trả về 400).
    Giải pháp: _strip_thinking() loại bỏ khối <think> khỏi mọi response.
    Với JSON mode: bỏ response_format json_object (không tương thích với thinking),
    dùng instruction trong prompt + parse bằng regex ở caller.
"""
import logging
import re

from llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Regex strip <think>...</think> kể cả khi bị cắt dở ở cuối do max_tokens
_THINK_PATTERN = re.compile(r'<think>.*?(?:</think>|$)', re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Loại bỏ khối <think>...</think> khỏi output của reasoning models."""
    cleaned = _THINK_PATTERN.sub("", text).strip()
    if not cleaned and "<think>" in text.lower():
        return "Xin lỗi, câu trả lời bị gián đoạn do quá dài. Vui lòng chia nhỏ câu hỏi hoặc hỏi chi tiết hơn."
    return cleaned or text.strip()


class GroqProvider(LLMProvider):

    def __init__(self, api_key: str, model_name: str):
        self.model_name = model_name
        try:
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=api_key)
            logger.info("[Groq] Khởi tạo | model=%s", model_name)
        except ImportError:
            raise ImportError(
                "groq package chưa được cài. Chạy: pip install groq>=0.9.0"
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
            raw = response.choices[0].message.content or self._fallback()
            # Strip thinking trace nếu là reasoning model (Qwen3, v.v.)
            return _strip_thinking(raw)
        except Exception as e:
            logger.error("[Groq/complete] Lỗi: %s", e)
            return self._fallback()

    async def complete_json(
        self,
        messages:   list[dict],
        system:     str,
        max_tokens: int = 800,
    ) -> str:
        """
        Gọi LLM với yêu cầu xuất JSON.

        Với Qwen3-32b (thinking model) trên Groq:
        - response_format=json_object không tương thích với thinking output → 400 error.
        - Groq không cho phép tắt thinking qua extra_body.
        - Giải pháp: KHÔNG dùng json_object, dùng text mode + strip thinking.
          Caller (_extract_json_robust) đã có regex fallback để bóc JSON từ text.
        """
        try:
            full_messages = [{"role": "system", "content": system}] + messages
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.0,
                # KHÔNG dùng response_format json_object — không tương thích với Qwen3 thinking
            )
            raw = response.choices[0].message.content or "{}"
            # Strip thinking trace trước khi trả về để parser JSON hoạt động đúng
            return _strip_thinking(raw)
        except Exception as e:
            logger.error("[Groq/JSON] Lỗi: %s", e)
            return "{}"

    async def complete_vision(
        self,
        image_path: str,
        prompt:     str,
        max_tokens: int = 4096,
    ) -> str:
        """Groq không hỗ trợ vision — trả về chuỗi rỗng."""
        logger.warning(
            "[Groq] complete_vision không được hỗ trợ. "
            "Hãy chọn Gemini hoặc GPT-4o cho slot OCR."
        )
        return ""

    @classmethod
    async def list_models(
        cls,
        api_key:  str,
        endpoint: str | None = None,
    ) -> list[str]:
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key)
            models = await client.models.list()
            return sorted([m.id for m in models.data])
        except Exception as e:
            logger.error("[Groq] list_models error: %s", e)
            return []

    @staticmethod
    def _fallback() -> str:
        return (
            "Hệ thống tạm thời không thể xử lý yêu cầu. "
            "Vui lòng thử lại sau."
        )

