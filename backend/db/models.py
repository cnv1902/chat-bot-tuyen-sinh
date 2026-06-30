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
import enum
import uuid
from sqlalchemy import String, Text, Boolean, DateTime, Integer, func, Uuid, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
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

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    STAFF_TRUONG = "STAFF_TRUONG"
    STAFF_NGANH = "STAFF_NGANH"
    CANDIDATE = "CANDIDATE"

class Account(Base):
    """
    Tài khoản người dùng (bao gồm Admin, Staff, Candidate).
    """
    __tablename__ = "accounts"

    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[RoleEnum] = mapped_column(SQLEnum(RoleEnum), default=RoleEnum.CANDIDATE, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Account username={self.username!r} role={self.role}>"

class StaffProfile(Base):
    """
    Hồ sơ bổ sung cho nhân viên (Staff).
    """
    __tablename__ = "staff_profiles"

    staff_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.account_id", ondelete="CASCADE"), unique=True)
    
    # role == STAFF_NGANH: major_codes lưu mảng mã ngành (VD: ["7480201", "7480101"])
    # role == STAFF_TRUONG: major_codes lưu NULL hoặc []
    major_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    current_load: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<StaffProfile id={self.staff_id} account_id={self.account_id}>"

class CandidateProfile(Base):
    """
    Hồ sơ bổ sung cho thí sinh (Candidate).
    """
    __tablename__ = "candidate_profiles"

    candidate_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.account_id", ondelete="CASCADE"), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    interested_majors: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<CandidateProfile id={self.candidate_id} email={self.email!r}>"

class Institute(Base):
    """
    Thông tin Trường/Viện đào tạo.
    """
    __tablename__ = "institutes"

    institute_code: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    institute_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    majors: Mapped[list["Major"]] = relationship(
        "Major", back_populates="institute", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Institute code={self.institute_code!r} name={self.institute_name!r}>"


class Major(Base):
    """
    Thông tin Ngành đào tạo thuộc Trường/Viện.
    """
    __tablename__ = "majors"

    major_code: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    institute_code: Mapped[str] = mapped_column(
        ForeignKey("institutes.institute_code", ondelete="CASCADE"), nullable=False
    )
    major_name: Mapped[str] = mapped_column(String(255), nullable=False)
    training_program: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_combinations: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    institute: Mapped["Institute"] = relationship("Institute", back_populates="majors")

    def __repr__(self) -> str:
        return f"<Major code={self.major_code!r} name={self.major_name!r}>"

class SubjectCombination(Base):
    """
    Tổ hợp môn xét tuyển.
    """
    __tablename__ = "subject_combinations"

    combo_code: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    subjects: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<SubjectCombination combo_code={self.combo_code!r} subjects={self.subjects!r}>"

class AdmissionMethod(Base):
    """
    Phương thức xét tuyển.
    """
    __tablename__ = "admission_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    method_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    method_name: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<AdmissionMethod year={self.year} code={self.method_code!r}>"

class AdmissionPlan(Base):
    """
    Đề án xét tuyển của một ngành trong một năm. (15 cột mới)
    """
    __tablename__ = "admission_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_xet_tuyen: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    ma_nganh: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nam: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ma_phuong_thuc: Mapped[str | None] = mapped_column(String(50), nullable=True)
    khoi: Mapped[str | None] = mapped_column(String(50), nullable=True)
    diem_chuan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hoc_ba_tbc_3_nam: Mapped[str | None] = mapped_column(String(50), nullable=True)
    diem_tot_nghiep: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tbc_3_nam_ngoai_ngu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hoc_luc_12: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nang_khieu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mon_nhan_he_so: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tieng_anh: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ngoai_ngu: Mapped[str | None] = mapped_column(String(50), nullable=True)
    he_so: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<AdmissionPlan ma_xet_tuyen={self.ma_xet_tuyen} nam={self.nam}>"

class AdmissionCode(Base):
    """
    Mã xét tuyển.
    """
    __tablename__ = "admission_codes"

    admission_code: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    major_code: Mapped[str] = mapped_column(String(50), nullable=False)
    program_name: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<AdmissionCode {self.admission_code} - {self.program_name}>"
