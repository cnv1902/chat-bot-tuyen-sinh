"""
llm/vllm.py
===========
vLLM provider — implement LLMProvider interface.
vLLM serve OpenAI-compatible API tại endpoint do admin cấu hình.

Hỗ trợ 2 chế độ triển khai:
  - Local:  endpoint = "http://localhost:8080"
  - Remote: endpoint = "https://api-vllm.itup.io.vn"  (cần api_key hợp lệ)

Lưu ý:
  - Sử dụng trực tiếp `httpx` thay vì `openai` SDK để có thể customize `User-Agent`.
    Nhiều server vLLM public/remote có cấu hình WAF (Cloudflare/Nginx) sẽ tự động chặn 
    (HTTP 403 - Your request was blocked) nếu User-Agent là OpenAI Python SDK.
"""
import base64
import logging
import re
import httpx

from llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Regex strip <think>...</think> kể cả khi bị cắt dở ở cuối do max_tokens
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str, is_json: bool = False) -> str:
    """Loại bỏ khối <think>...</think> khỏi output của reasoning models."""
    cleaned = _THINK_RE.sub("", text).strip()
    # Nếu text chỉ toàn <think> bị cắt dở mà không có câu trả lời thực tế
    if not cleaned and "<think>" in text.lower():
        if is_json:
            return "{}"
        return "Xin lỗi, câu trả lời bị gián đoạn do quá dài. Vui lòng chia nhỏ câu hỏi hoặc hỏi chi tiết hơn."
    return cleaned or text.strip()


class VLLMProvider(LLMProvider):
    # Singleton cache cho httpx.AsyncClient
    _client_cache: dict[str, httpx.AsyncClient] = {}

    def __init__(self, api_key: str, model_name: str, endpoint: str):
        """
        Args:
            endpoint:   Base URL của vLLM server, KHÔNG bao gồm /v1.
                        Local:  "http://localhost:8080"
                        Remote: "https://api-vllm.itup.io.vn"
            model_name: Tên model đang serve trên vLLM (nhập tay từ Admin UI).
            api_key:    Bearer token nếu server yêu cầu xác thực.
        """
        self.model_name = model_name
        self.api_key    = (api_key or "").strip()
        self.endpoint   = endpoint.rstrip("/") if endpoint else ""

        if not self.endpoint:
            raise ValueError(
                "vLLM endpoint chưa được cấu hình. "
                "Vào Admin → Credentials → vLLM Server URL Endpoint."
            )

        # Cấu hình base headers để vượt qua WAF rules khắt khe
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _get_client(self) -> httpx.AsyncClient:
        cache_key = f"{self.endpoint}:{self.api_key}"
        if cache_key not in VLLMProvider._client_cache:
            VLLMProvider._client_cache[cache_key] = httpx.AsyncClient(timeout=120.0)
            logger.info("[vLLM] Tạo HTTP client mới | key=%s", cache_key)
        return VLLMProvider._client_cache[cache_key]

    async def _post_chat_completions(self, payload: dict, is_json: bool = False) -> str:
        """Helper gọi API /v1/chat/completions"""
        url = f"{self.endpoint}/v1/chat/completions"
        client = self._get_client()
        
        response = await client.post(url, headers=self.headers, json=payload)
        
        # Quăng lỗi nếu status code >= 400
        response.raise_for_status()
        
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            raw_content = data["choices"][0]["message"].get("content", "")
            return _strip_thinking(raw_content, is_json=is_json)
        return self._fallback()

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
            payload = {
                "model": self.model_name,
                "messages": full_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if top_p is not None:
                payload["top_p"] = top_p
                
            return await self._post_chat_completions(payload, is_json=False)
            
        except httpx.HTTPStatusError as e:
            logger.error("[vLLM/complete] HTTP Lỗi %s: %s", e.response.status_code, e.response.text[:200])
            return self._fallback()
        except Exception as e:
            logger.error("[vLLM/complete] Lỗi hệ thống: %s", e)
            return self._fallback()

    async def complete_json(
        self,
        messages:   list[dict],
        system:     str,
        max_tokens: int = 800,
    ) -> str:
        try:
            full_messages = [{"role": "system", "content": system}] + messages
            payload = {
                "model": self.model_name,
                "messages": full_messages,
                "max_tokens": max_tokens,
                "temperature": 0.0,
            }
            return await self._post_chat_completions(payload, is_json=True)
            
        except httpx.HTTPStatusError as e:
            logger.error("[vLLM/JSON] HTTP Lỗi %s: %s", e.response.status_code, e.response.text[:200])
            return "{}"
        except Exception as e:
            logger.error("[vLLM/JSON] Lỗi hệ thống: %s", e)
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
                
            payload = {
                "model": self.model_name,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }},
                    ],
                }],
                "max_tokens": max_tokens,
                "temperature": 0.0,
            }
            return await self._post_chat_completions(payload)
            
        except httpx.HTTPStatusError as e:
            logger.error("[vLLM/Vision] HTTP Lỗi %s: %s", e.response.status_code, e.response.text[:200])
            return ""
        except Exception as e:
            logger.error("[vLLM/Vision] Lỗi hệ thống: %s", e)
            return ""

    @classmethod
    async def list_models(
        cls,
        api_key:  str,
        endpoint: str | None = None,
    ) -> list[str]:
        """
        Thử lấy danh sách model từ GET /v1/models bằng HTTP request thuần.
        """
        if not endpoint:
            return []
            
        url = f"{endpoint.rstrip('/')}/v1/models"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key.strip()}"
            
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                names = [m["id"] for m in data.get("data", []) if "id" in m]
                logger.info("[vLLM/list_models] Tìm thấy %d model tại %s", len(names), endpoint)
                return names
        except Exception as e:
            logger.info(
                "[vLLM/list_models] Không thể load danh sách từ server (%s) → admin nhập tay.", e
            )
            return []

    @staticmethod
    def _fallback() -> str:
        return (
            "Hệ thống tạm thời không thể xử lý yêu cầu. "
            "Vui lòng thử lại sau."
        )
