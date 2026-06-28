"""
db/models.py
============
SQLAlchemy ORM models cho LLM configuration và ETL document tracking.

Bảng:
  - llm_providers:      Lưu API key và endpoint của từng provider
  - llm_slots:          Lưu provider + model được chọn cho từng slot (ocr/chat)
  - uploaded_documents: Lưu lịch sử và trạng thái xử lý file tài liệu tuyển sinh

Schema thiết kế tối giản — production nên mã hóa api_key bằng secrets manager.
"""
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from db.connection import Base


class LLMProvider(Base):
    """
    Credentials của từng LLM provider.

    Fields:
        provider:   Tên provider duy nhất. Giá trị hợp lệ: "gemini" | "openai" | "groq" | "vllm"
        api_key:    API key dạng plaintext. Production nên encrypt trước khi lưu.
        endpoint:   URL của inference server (dùng cho vLLM tự host).
        is_active:  Provider có đang được bật hay không.
        updated_at: Thời điểm cập nhật gần nhất (auto-update bởi DB trigger).
    """
    __tablename__ = "llm_providers"

    id:         Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider:   Mapped[str]       = mapped_column(String(20), unique=True, nullable=False, index=True)
    api_key:    Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoint:   Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active:  Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime]  = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<LLMProvider provider={self.provider!r} active={self.is_active}>"


class LLMSlot(Base):
    """
    Cấu hình model đang được sử dụng cho từng nhiệm vụ cụ thể.

    Hiện có 2 slot:
        "ocr"  → Provider/model dùng cho vision_extractor (phân tích PDF ảnh)
        "chat" → Provider/model dùng cho agent/nodes.py (classify + generate)

    Thay đổi slot có hiệu lực ngay lập tức (không cần restart),
    vì _load_provider() trong llm/__init__.py đọc DB mỗi request.
    """
    __tablename__ = "llm_slots"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot:       Mapped[str]      = mapped_column(String(10), unique=True, nullable=False, index=True)
    provider:   Mapped[str]      = mapped_column(String(20), nullable=False)
    model_name: Mapped[str]      = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<LLMSlot slot={self.slot!r} provider={self.provider!r} model={self.model_name!r}>"


class UploadedDocument(Base):
    """
    Lịch sử và trạng thái xử lý file tài liệu tuyển sinh.

    Trạng thái (status):
        "processing" → Đang được xử lý bởi background task
        "success"    → Đã OCR, chunk và index vào Qdrant thành công
        "failed"     → Xảy ra lỗi trong quá trình xử lý

    Fields:
        filename:   Tên file gốc được upload
        year:       Năm tuyển sinh áp dụng cho tài liệu này
        status:     Trạng thái xử lý hiện tại
        message:    Thông tin kết quả (số trang/chunks khi thành công, mô tả lỗi khi thất bại)
        created_at: Thời điểm upload (bất biến)
        updated_at: Thời điểm cập nhật trạng thái gần nhất
    """
    __tablename__ = "uploaded_documents"

    id:         Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename:   Mapped[str]       = mapped_column(String(255), nullable=False)
    year:       Mapped[int]       = mapped_column(Integer, nullable=False)
    status:     Mapped[str]       = mapped_column(String(20), default="processing", nullable=False)
    message:    Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]  = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime]  = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<UploadedDocument id={self.id} file={self.filename!r} status={self.status!r}>"
