from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Any, Optional
import uuid
import pandas as pd
import io
import os
import shutil

from db.connection import get_db
from db.models import Account, StaffProfile, RoleEnum
from api.routers.auth import get_password_hash
from core.staff_routing import sync_staff_to_redis
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/staff",
    tags=["Staff"]
)

@router.post("/import")
async def import_staff(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Vui lòng tải lên file Excel (.xlsx, .xls)")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        required_cols = {"Họ tên", "Số điện thoại", "Email", "Đơn vị", "Mật khẩu", "Vai trò", "Chương trình đào tạo"}
        if not required_cols.issubset(df.columns):
            raise HTTPException(
                status_code=400, 
                detail=f"File Excel thiếu cột. Các cột bắt buộc: {', '.join(required_cols)}"
            )

        success_count = 0
        
        for index, row in df.iterrows():
            email = str(row.get("Email", "")).strip()
            if not email or email.lower() == 'nan':
                continue
                
            full_name = str(row.get("Họ tên", "")).strip()
            if full_name.lower() == 'nan': full_name = None
            phone = str(row.get("Số điện thoại", "")).strip()
            if phone.lower() == 'nan': phone = None
            unit_code = str(row.get("Đơn vị", "")).strip()
            if unit_code.lower() == 'nan': unit_code = None

            raw_password = str(row.get("Mật khẩu", "")).strip()
            role_str = str(row.get("Vai trò", "")).strip().upper()
            programs_str = str(row.get("Chương trình đào tạo", "")).strip()
            
            if role_str not in [RoleEnum.STAFF_TRUONG.value, RoleEnum.STAFF_NGANH.value]:
                continue # Skip invalid roles
                
            role_enum = RoleEnum(role_str)
            
            # Process programs
            if role_enum == RoleEnum.STAFF_TRUONG:
                managed_programs = None
            else:
                managed_programs = programs_str if programs_str and programs_str.lower() != 'nan' else None

            # Check if account exists
            stmt = select(Account).where(Account.username == email)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

            if account:
                # Update existing account
                if raw_password and raw_password.lower() != 'nan':
                    account.password_hash = get_password_hash(raw_password)
                account.role = role_enum
                account.is_active = True
                
                # Check staff profile
                stmt_profile = select(StaffProfile).where(StaffProfile.account_id == account.account_id)
                res_profile = await db.execute(stmt_profile)
                profile = res_profile.scalar_one_or_none()
                
                if profile:
                    profile.managed_programs = managed_programs
                    profile.full_name = full_name
                    profile.phone = phone
                    profile.unit_code = unit_code
                else:
                    new_profile = StaffProfile(
                        account_id=account.account_id, 
                        managed_programs=managed_programs,
                        full_name=full_name,
                        phone=phone,
                        unit_code=unit_code
                    )
                    db.add(new_profile)
            else:
                # Create new account
                if not raw_password or raw_password.lower() == 'nan':
                    raw_password = "123" # Default password if not provided
                    
                new_account = Account(
                    username=email,
                    password_hash=get_password_hash(raw_password),
                    role=role_enum,
                    is_active=True
                )
                db.add(new_account)
                await db.flush() # To get account_id
                
                new_profile = StaffProfile(
                    account_id=new_account.account_id,
                    managed_programs=managed_programs,
                    full_name=full_name,
                    phone=phone,
                    unit_code=unit_code,
                    is_online=False,
                    current_load=0
                )
                db.add(new_profile)
                
            success_count += 1
            
        await db.commit()
        await sync_staff_to_redis(db)
        return {"message": "Import thành công", "imported_count": success_count}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi import dữ liệu: {str(e)}")

@router.get("/list")
async def list_staff(db: AsyncSession = Depends(get_db)):
    try:
        stmt = (
            select(Account, StaffProfile)
            .outerjoin(StaffProfile, Account.account_id == StaffProfile.account_id)
            .where(Account.role.in_([RoleEnum.STAFF_TRUONG, RoleEnum.STAFF_NGANH, RoleEnum.ADMIN]))
        )
        result = await db.execute(stmt)
        
        response = []
        for account, profile in result.all():
            response.append({
                "id": str(account.account_id),
                "email": account.username,
                "role": account.role.value,
                "is_active": account.is_active,
                "managed_programs": profile.managed_programs if profile else "",
                "full_name": profile.full_name if profile else None,
                "phone": profile.phone if profile else None,
                "unit_code": profile.unit_code if profile else None,
                "avatar_url": profile.avatar_url if profile else None,
            })
            
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách cán bộ: {str(e)}")

def _save_avatar(avatar: UploadFile) -> Optional[str]:
    if not avatar:
        return None
    
    # 1. Bảo mật Backend (File Validation): Bắt buộc kiểm tra định dạng
    if not avatar.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File upload không phải là định dạng ảnh.")
    
    # 2. Giới hạn dung lượng: < 5MB = 5 * 1024 * 1024 bytes
    file_size = 0
    avatar.file.seek(0, os.SEEK_END)
    file_size = avatar.file.tell()
    avatar.file.seek(0)
    if file_size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh avatar không được vượt quá 5MB.")

    ext = os.path.splitext(avatar.filename)[1]
    if not ext: ext = ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join("uploads", "avatars", filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)
        
    return f"/uploads/avatars/{filename}"

@router.post("/create")
async def create_staff(
    email: str = Form(...),
    password: Optional[str] = Form(None),
    role: str = Form(...),
    managed_programs: str = Form(""),
    is_active: bool = Form(True),
    full_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    unit_code: Optional[str] = Form(None),
    avatar: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    email = email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email không được để trống")
        
    role_str = role.strip().upper()
    if role_str not in [RoleEnum.STAFF_TRUONG.value, RoleEnum.STAFF_NGANH.value, RoleEnum.ADMIN.value]:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
        
    role_enum = RoleEnum(role_str)
    
    managed_programs = managed_programs.strip()
    if role_enum == RoleEnum.STAFF_TRUONG:
        managed_programs = None

    try:
        stmt = select(Account).where(Account.username == email)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if account:
            raise HTTPException(status_code=400, detail="Email đã tồn tại")

        avatar_url = _save_avatar(avatar)

        raw_password = password if password else "123"
        new_account = Account(
            username=email,
            password_hash=get_password_hash(raw_password),
            role=role_enum,
            is_active=is_active
        )
        db.add(new_account)
        await db.flush()
        
        new_profile = StaffProfile(
            account_id=new_account.account_id,
            managed_programs=managed_programs,
            full_name=full_name if full_name else None,
            phone=phone if phone else None,
            unit_code=unit_code if unit_code else None,
            avatar_url=avatar_url,
            is_online=False,
            current_load=0
        )
        db.add(new_profile)
            
        await db.commit()
        await sync_staff_to_redis(db)
        return {"message": "Thêm cán bộ thành công"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi thêm cán bộ: {str(e)}")

@router.put("/update/{account_id}")
async def update_staff(
    account_id: str,
    password: Optional[str] = Form(None),
    role: str = Form(...),
    managed_programs: str = Form(""),
    is_active: bool = Form(True),
    full_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    unit_code: Optional[str] = Form(None),
    avatar: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        acc_uuid = uuid.UUID(account_id)
        stmt = select(Account).where(Account.account_id == acc_uuid)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản cán bộ")
            
        role_str = role.strip().upper()
        if role_str not in [RoleEnum.STAFF_TRUONG.value, RoleEnum.STAFF_NGANH.value, RoleEnum.ADMIN.value]:
            raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
            
        role_enum = RoleEnum(role_str)
        
        managed_programs = managed_programs.strip()
        if role_enum == RoleEnum.STAFF_TRUONG:
            managed_programs = None
        
        if password:
            account.password_hash = get_password_hash(password)
            
        account.role = role_enum
        account.is_active = is_active
        
        stmt_profile = select(StaffProfile).where(StaffProfile.account_id == acc_uuid)
        res_profile = await db.execute(stmt_profile)
        profile = res_profile.scalar_one_or_none()
        
        avatar_url = _save_avatar(avatar)

        if profile:
            profile.managed_programs = managed_programs
            profile.full_name = full_name if full_name else None
            profile.phone = phone if phone else None
            profile.unit_code = unit_code if unit_code else None
            if avatar_url: profile.avatar_url = avatar_url
        else:
            new_profile = StaffProfile(
                account_id=acc_uuid, 
                managed_programs=managed_programs,
                full_name=full_name,
                phone=phone,
                unit_code=unit_code,
                avatar_url=avatar_url
            )
            db.add(new_profile)
            
        await db.commit()
        await sync_staff_to_redis(db)
        return {"message": "Cập nhật cán bộ thành công"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật cán bộ: {str(e)}")

class DeleteBulkRequest(BaseModel):
    ids: List[str]

@router.delete("/delete/{account_id}")
async def delete_staff(account_id: str, db: AsyncSession = Depends(get_db)):
    try:
        acc_uuid = uuid.UUID(account_id)
        stmt = delete(Account).where(Account.account_id == acc_uuid)
        await db.execute(stmt)
        await db.commit()
        await sync_staff_to_redis(db)
        return {"message": "Xóa cán bộ thành công"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa cán bộ: {str(e)}")

@router.post("/bulk-delete")
async def bulk_delete_staff(req: DeleteBulkRequest, db: AsyncSession = Depends(get_db)):
    try:
        uuids = [uuid.UUID(i) for i in req.ids]
        stmt = delete(Account).where(Account.account_id.in_(uuids))
        await db.execute(stmt)
        await db.commit()
        await sync_staff_to_redis(db)
        return {"message": f"Đã xóa {len(req.ids)} cán bộ thành công"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa hàng loạt: {str(e)}")
