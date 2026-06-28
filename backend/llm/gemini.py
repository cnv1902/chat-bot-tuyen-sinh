"""
llm/gemini.py
=============
Google Gemini provider — implement LLMProvider interface.
Hỗ trợ cả text completion, JSON mode, và vision (OCR).

QUAN TRỌNG: Dùng google-generativeai SDK (sync) nhưng wrap trong async methods.
            Sẽ được upgrade sang google-genai (async native) trong phiên bản sau.
"""
import base64
import logging
import time

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import GoogleAPIError

from llm.base import LLMProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # giây


class GeminiProvider(LLMProvider):

    def __init__(self, api_key: str, model_name: str):
        """
        Args:
            api_key:    Google API key.
            model_name: Tên model, vd "gemini-2.5-flash".
        """
        self.api_key    = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        logger.info("[Gemini] Khởi tạo | model=%s", model_name)

    # ── Text completion ─────────────────────────────────────────────────────

    async def complete(
        self,
        messages:    list[dict],
        system:      str,
        max_tokens:  int   = 2048,
        temperature: float = 0.0,
        top_p:       float | None = None,
    ) -> str:
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system,
            )
            history = self._convert_messages(messages)
            if not history:
                return self._fallback()

            gen_config_kwargs: dict = dict(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            if top_p is not None:
                gen_config_kwargs["top_p"] = top_p

            response = model.generate_content(
                history,
                generation_config=GenerationConfig(**gen_config_kwargs),
            )
            if not response.candidates:
                logger.error("[Gemini/complete] Không có candidates trong response.")
                return self._fallback()
            return response.text

        except GoogleAPIError as e:
            logger.error("[Gemini/complete] API error: %s", e)
            return self._fallback()
        except Exception as e:
            logger.error("[Gemini/complete] Lỗi không xác định: %s", e)
            return self._fallback()

    # ── JSON completion ─────────────────────────────────────────────────────

    async def complete_json(
        self,
        messages:   list[dict],
        system:     str,
        max_tokens: int = 800,
    ) -> str:
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    max_output_tokens=max_tokens,
                    temperature=0.0,
                ),
            )
            history = self._convert_messages(messages)
            if not history:
                return "{}"

            response = model.generate_content(history)
            if not response.candidates:
                return "{}"
            return response.text

        except Exception as e:
            logger.error("[Gemini/JSON] Lỗi: %s", e)
            return "{}"

    # ── Vision / OCR ────────────────────────────────────────────────────────

    async def complete_vision(
        self,
        image_path: str,
        prompt:     str,
        max_tokens: int = 4096,
    ) -> str:
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    max_output_tokens=max_tokens,
                    temperature=0.0,
                ),
            )
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")

            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    response = model.generate_content([
                        {"mime_type": "image/jpeg", "data": img_b64},
                        prompt,
                    ])
                    return response.text.strip()
                except GoogleAPIError as e:
                    logger.warning(
                        "[Gemini/Vision] Lỗi attempt %d/%d | file=%s: %s",
                        attempt, _MAX_RETRIES, image_path, e,
                    )
                    if attempt < _MAX_RETRIES:
                        time.sleep(_RETRY_BASE_DELAY * attempt)
                    else:
                        raise

        except Exception as e:
            logger.error("[Gemini/Vision] Lỗi trên %s: %s", image_path, e)
            return ""

    # ── List models ─────────────────────────────────────────────────────────

    @classmethod
    async def list_models(
        cls,
        api_key:  str,
        endpoint: str | None = None,
    ) -> list[str]:
        try:
            genai.configure(api_key=api_key)
            models = genai.list_models()
            return sorted([
                m.name.replace("models/", "")
                for m in models
                if "generateContent" in m.supported_generation_methods
            ])
        except Exception as e:
            logger.error("[Gemini] list_models error: %s", e)
            return []

    # ── Private helpers ──────────────────────────────────────────────────────

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert OpenAI message format → Gemini parts format."""
        result = []
        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue
            role = "model" if msg.get("role") == "assistant" else "user"
            result.append({"role": role, "parts": [content]})
        return result

    @staticmethod
    def _fallback() -> str:
        return (
            "Hệ thống tạm thời không thể xử lý yêu cầu. "
            "Vui lòng thử lại sau."
        )
