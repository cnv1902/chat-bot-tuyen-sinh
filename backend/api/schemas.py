"""
api/schemas.py
==============
Pydantic v2 Models — Định nghĩa contract dữ liệu đầu vào/đầu ra API.

Chuẩn Pydantic v2:
- model_config = ConfigDict(...)    thay vì class Config
- @field_validator(mode='before')   thay vì @validator
- Field(..., description=...)       vẫn giữ nguyên, tương thích v2
- Tất cả model đều có model_config json_schema_extra để tự sinh OpenAPI docs
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===========================================================================
# REQUEST MODELS
# ===========================================================================

class ChatRequest(BaseModel):
    """
    Payload đầu vào cho POST /api/chat.

    session_id: Tùy chọn. Client tự sinh và giữ UUID qua các lượt chat.
                Nếu bỏ qua, server tự tạo UUID mới → phiên chat mới hoàn toàn.
    message:    Câu hỏi của thí sinh. Bắt buộc, không được rỗng.
    """

    model_config = ConfigDict(
        # Hiển thị ví dụ trong /docs (Swagger UI)
        json_schema_extra={
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "message": "Điểm chuẩn ngành Công nghệ thông tin năm 2026 là bao nhiêu?",
            }
        }
    )

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description=(
            "UUID định danh phiên chat. "
            "Client nên giữ giá trị này và gửi lại ở các request tiếp theo "
            "để duy trì lịch sử hội thoại. "
            "Nếu không cung cấp, server tự tạo UUID mới."
        ),
        min_length=1,
        max_length=128,
    )

    message: str = Field(
        ...,
        description="Câu hỏi tuyển sinh của thí sinh. Không được để trống.",
        min_length=1,
        max_length=2000,
    )

    # --- Validators ---

    @field_validator("session_id", mode="before")
    @classmethod
    def sanitize_session_id(cls, v: Any) -> str:
        """
        Chuẩn hóa session_id:
        - Nếu None hoặc chuỗi rỗng → tự sinh UUID mới
        - Strip whitespace thừa
        - Giữ nguyên giá trị hợp lệ của client
        """
        if not v or (isinstance(v, str) and not v.strip()):
            return str(uuid.uuid4())
        return str(v).strip()

    @field_validator("message", mode="before")
    @classmethod
    def sanitize_message(cls, v: Any) -> str:
        """
        Chuẩn hóa message:
        - Strip whitespace đầu/cuối
        - Chuẩn hóa khoảng trắng trong (nhiều space → 1 space)
        - Reject nếu sau khi strip vẫn rỗng
        """
        if not isinstance(v, str):
            raise ValueError("message phải là chuỗi văn bản.")
        cleaned = " ".join(v.split())   # Chuẩn hóa whitespace nội bộ
        if not cleaned:
            raise ValueError("message không được để trống sau khi loại bỏ khoảng trắng.")
        return cleaned


# ===========================================================================
# RESPONSE MODELS
# ===========================================================================

class ChatResponse(BaseModel):
    """
    Payload đầu ra của POST /api/chat.

    session_id: Echo lại session_id để client biết/cập nhật.
    answer:     Câu trả lời từ Gemini (hoặc fallback message).
    sources:    Danh sách file nguồn tài liệu (có thứ tự, deduplicate).
                Rỗng nếu là fallback response hoặc không có data.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "answer": (
                    "Điểm chuẩn ngành Công nghệ thông tin (mã ngành 7480201) "
                    "của Trường Đại học Vinh năm 2026 là **24.5 điểm**.\n\n"
                    "*Nguồn: Đề án tuyển sinh 2026, trang 12*"
                ),
                "sources": ["DeAn_TuyenSinh_2026.pdf"],
            }
        }
    )

    session_id: str = Field(
        ...,
        description="UUID phiên chat — client giữ lại để gửi ở request tiếp theo.",
    )

    answer: str = Field(
        ...,
        description="Câu trả lời của chatbot. Có thể chứa Markdown formatting.",
    )

    sources: list[str] = Field(
        default_factory=list,
        description=(
            "Danh sách tên file tài liệu nguồn được tham chiếu trong câu trả lời. "
            "Có thứ tự (file liên quan nhất trước), không có phần tử trùng lặp."
        ),
    )


class HealthResponse(BaseModel):
    """
    Payload đầu ra của GET /health.
    Mô tả trạng thái của từng thành phần hạ tầng.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "components": {
                    "redis":   {"status": "ok", "latency_ms": 0.82},
                    "qdrant":  {"status": "ok"},
                    "embedder": {"status": "ok", "model": "BAAI/bge-m3", "dimension": 1024},
                },
            }
        }
    )

    status: str = Field(
        ...,
        description="Trạng thái tổng thể: 'ok' | 'degraded' | 'error'",
    )

    components: dict[str, Any] = Field(
        default_factory=dict,
        description="Chi tiết trạng thái từng component (Redis, Qdrant, Embedder).",
    )


class ErrorResponse(BaseModel):
    """
    Payload lỗi chuẩn hóa trả về khi có exception.
    Dùng cho exception handlers trong main.py.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "validation_error",
                "detail": "message không được để trống.",
                "request_id": "a1b2c3d4",
            }
        }
    )

    error: str = Field(..., description="Mã lỗi ngắn gọn (snake_case).")
    detail: str = Field(..., description="Mô tả lỗi chi tiết cho developer.")
    request_id: str | None = Field(
        default=None,
        description="ID request để trace log (nếu có).",
    )
