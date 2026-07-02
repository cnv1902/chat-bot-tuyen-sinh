"""
api/routers/auth.py
===================
Xử lý xác thực người dùng, JWT token và login.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
import jwt

from db.connection import get_db
from db.models import Account, RoleEnum
from core.email_service import generate_and_store_otp, send_otp_email, verify_otp_from_redis

router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)

# Configuration cho mật khẩu và JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-tuyen-sinh-dhv-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 ngày

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str

class SendOTPRequest(BaseModel):
    email: str

class VerifyFirstLoginRequest(BaseModel):
    email: str
    otp_code: str
    new_password: str

class GoogleLoginRequest(BaseModel):
    email: str
    google_token: str

# --- Utilities ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Dependencies ---
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency dùng để giải mã JWT và kiểm tra token.
    Tạm thời BỎ QUA việc kiểm tra Role. Chỉ cần token hợp lệ là cho phép đi qua (pass-through).
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_id: str = payload.get("sub")
        role: str = payload.get("role")
        if account_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ (không chứa account_id)",
            )
        return {"account_id": account_id, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không thể giải mã token",
        )

# --- Endpoints ---
@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """
    API Đăng nhập. Nhận payload JSON có username và password.
    """
    # Tìm account trong DB
    stmt = select(Account).where(Account.username == request.username)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu"
        )
    
    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa"
        )
    
    # Kiểm tra mật khẩu
    if not verify_password(request.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu"
        )
    
    # Chốt chặn: Yêu cầu xác thực lần đầu (bỏ qua cho ADMIN)
    if not account.is_verified and account.role != RoleEnum.ADMIN:
        return {"status": "require_verification", "email": account.username}
    
    # Tạo JWT Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(account.account_id), "role": account.role.value},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=account.role.value
    )


@router.post("/send-otp")
async def send_otp(request: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    """
    Tạo và gửi mã OTP qua email cho lần đăng nhập đầu tiên.
    """
    # Kiểm tra tồn tại Account
    stmt = select(Account).where(Account.username == request.email)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản với email này"
        )
    
    if account.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản đã được xác thực"
        )

    # Sinh OTP và gửi
    try:
        otp_code = generate_and_store_otp(request.email)
        success = await send_otp_email(request.email, otp_code)
        
        if success:
            return {"detail": "Đã gửi mã OTP thành công."}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi khi gửi email."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống: {str(e)}"
        )


@router.post("/verify-first-login")
async def verify_first_login(request: VerifyFirstLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Xác nhận OTP, đổi mật khẩu và cập nhật trạng thái verified.
    """
    # So khớp OTP từ Redis
    is_valid = verify_otp_from_redis(request.email, request.otp_code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không chính xác hoặc đã hết hạn"
        )

    # Tìm account để cập nhật
    stmt = select(Account).where(Account.username == request.email)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản không tồn tại"
        )

    # Cập nhật thông tin
    account.password_hash = get_password_hash(request.new_password)
    account.is_verified = True
    
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi khi cập nhật cơ sở dữ liệu"
        )

    # Trả về Token đăng nhập
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(account.account_id), "role": account.role.value},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=account.role.value
    )


@router.post("/google-login")
async def google_login(request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Xử lý Đăng nhập qua Google SSO.
    """
    stmt = select(Account).where(Account.username == request.email)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        from db.models import CandidateProfile
        account = Account(
            username=request.email,
            password_hash=get_password_hash("google_sso"),
            role=RoleEnum.CANDIDATE,
            is_active=True,
            is_verified=True
        )
        db.add(account)
        await db.flush()
        
        profile = CandidateProfile(
            account_id=account.account_id,
            email=request.email
        )
        db.add(profile)
        await db.commit()

    if not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa"
        )

    # Đánh dấu đã xác thực nếu Google trả về thành công
    if not account.is_verified:
        account.is_verified = True
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi lưu trạng thái xác thực."
            )

    # Tạo JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(account.account_id), "role": account.role.value},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=account.role.value
    )

@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import uuid
    account_uuid = uuid.UUID(current_user.get("account_id"))
    stmt = select(Account).where(Account.account_id == account_uuid)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_data = {
        "id": str(account.account_id),
        "email": account.username,
        "role": account.role.value,
        "is_active": account.is_active,
        "is_verified": account.is_verified,
    }
    
    # Lấy thêm thông tin từ StaffProfile nếu có
    from db.models import StaffProfile
    prof_stmt = select(StaffProfile).where(StaffProfile.account_id == account_uuid)
    prof_res = await db.execute(prof_stmt)
    prof = prof_res.scalar_one_or_none()
    
    if prof:
        user_data["full_name"] = prof.full_name
        user_data["phone"] = prof.phone
        user_data["unit_code"] = prof.unit_code
        user_data["avatar_url"] = prof.avatar_url
        user_data["managed_programs"] = prof.managed_programs
        user_data["is_online"] = prof.is_online
    else:
        # Nếu không có StaffProfile, kiểm tra CandidateProfile
        from db.models import CandidateProfile
        cand_stmt = select(CandidateProfile).where(CandidateProfile.account_id == account_uuid)
        cand_res = await db.execute(cand_stmt)
        cand_prof = cand_res.scalar_one_or_none()
        if cand_prof:
            user_data["full_name"] = cand_prof.full_name
            user_data["phone"] = cand_prof.phone_number
        
    return user_data
