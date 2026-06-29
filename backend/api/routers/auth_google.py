import os
from datetime import timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.connection import get_db
from db.models import Account, CandidateProfile, RoleEnum
from api.routers.auth import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

class GoogleLoginRequest(BaseModel):
    code: str

@router.post("/google")
async def google_login(request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Nhận authorization code từ frontend, đổi lấy token và thông tin user từ Google.
    Tạo hoặc đăng nhập tài khoản cho ứng viên.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = "http://localhost:5173/auth/google/callback"
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on the server."
        )
    
    # 1. Đổi code lấy access_token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": request.code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=token_data)
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange token: {token_res.text}"
            )
            
        access_token = token_res.json().get("access_token")
        
        # 2. Lấy thông tin user
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_res = await client.get(userinfo_url, headers=headers)
        
        if userinfo_res.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user info from Google."
            )
            
        user_info = userinfo_res.json()
        email = user_info.get("email")
        full_name = user_info.get("name")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account does not have an email."
            )
            
    # 3. Kiểm tra DB xem tài khoản có chưa
    stmt = select(Account).where(Account.username == email)
    result = await db.execute(stmt)
    account = result.scalars().first()
    
    if not account:
        # Nếu chưa có, tạo tài khoản mới (không có mật khẩu)
        account = Account(
            username=email,
            password_hash=None, # OAuth user
            role=RoleEnum.CANDIDATE,
            is_active=True
        )
        db.add(account)
        await db.flush() # Lấy account.account_id
        
        # Tạo CandidateProfile
        candidate_profile = CandidateProfile(
            account_id=account.account_id,
            email=email,
            full_name=full_name,
            # phone_number và interested_majors để trống
        )
        db.add(candidate_profile)
        await db.commit()
    elif account.role != RoleEnum.CANDIDATE:
        # Tùy chọn: Chặn nếu email này đã là ADMIN hoặc STAFF
        # Nhưng ở đây ta cứ cho phép đăng nhập nếu muốn.
        pass
        
    # 4. Sinh JWT token của hệ thống
    access_token_expires = timedelta(days=7) # 7 days
    token = create_access_token(
        data={"sub": str(account.account_id), "role": account.role},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "account_id": str(account.account_id),
            "username": account.username,
            "role": account.role,
            "full_name": full_name
        }
    }
