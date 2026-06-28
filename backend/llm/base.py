"""
llm/base.py
===========
Abstract base class cho tất cả LLM provider.
Mọi provider PHẢI implement đủ 4 method này.
Interface tối giản — chỉ những gì hệ thống thực sự cần.
"""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Interface chuẩn cho mọi LLM provider.
    Implement đầy đủ để đảm bảo tương thích với toàn bộ hệ thống.
    """

    @abstractmethod
    async def complete(
        self,
        messages:    list[dict],
        system:      str,
        max_tokens:  int   = 2048,
        temperature: float = 0.0,
        top_p:       float | None = None,
    ) -> str:
        """
        Sinh văn bản từ danh sách messages.
        Dùng cho: generate_answer trong agent/nodes.py

        messages format: [{"role": "user"|"assistant", "content": "..."}]
        top_p: Giới hạn không gian chọn token (nucleus sampling).
               None = dùng default của provider.
               0.1  = chỉ chọn trong top 10% token có xác suất cao nhất.
        Trả về: chuỗi văn bản, KHÔNG raise exception ra ngoài.
        Fallback: trả về thông báo lỗi thân thiện người dùng.
        """
        ...

    @abstractmethod
    async def complete_json(
        self,
        messages:   list[dict],
        system:     str,
        max_tokens: int = 800,
    ) -> str:
        """
        Sinh JSON string từ messages.
        Dùng cho: classify_intent trong agent/nodes.py

        Trả về: chuỗi JSON hợp lệ hoặc '{}' nếu lỗi.
        KHÔNG raise exception ra ngoài.
        """
        ...

    @abstractmethod
    async def complete_vision(
        self,
        image_path: str,
        prompt:     str,
        max_tokens: int = 4096,
    ) -> str:
        """
        Phân tích ảnh và sinh văn bản Markdown.
        Dùng cho: vision_extractor.py (OCR pipeline)

        image_path: Đường dẫn tuyệt đối tới file JPEG.
        Trả về: Markdown string hoặc '' nếu lỗi.
        KHÔNG raise exception ra ngoài.
        """
        ...

    @classmethod
    @abstractmethod
    async def list_models(
        cls,
        api_key:  str,
        endpoint: str | None = None,
    ) -> list[str]:
        """
        Lấy danh sách model khả dụng từ provider API.
        Dùng cho: Admin UI dropdown chọn model.

        Trả về: list tên model, [] nếu lỗi hoặc không kết nối được.
        KHÔNG raise exception ra ngoài.
        """
        ...
