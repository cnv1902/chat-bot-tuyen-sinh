from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Dict, Any, Optional
import uuid
import pandas as pd
import io
from pydantic import BaseModel

from db.connection import get_db
from db.models import Account, StaffProfile, RoleEnum
from api.routers.auth import get_password_hash

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
        
        required_cols = {"Email", "Mật Khẩu", "Vai Trò", "Ngành Phụ Trách"}
        if not required_cols.issubset(df.columns):
            raise HTTPException(
                status_code=400, 
                detail=f"File Excel thiếu cột. Các cột bắt buộc: {', '.join(required_cols)}"
            )

        success_count = 0
        
        # FastAPI / SQLAlchemy AsyncSession default doesn't auto-commit, 
        # so we are implicitly in a transaction. We will commit at the end.
        for index, row in df.iterrows():
            email = str(row.get("Email", "")).strip()
            if not email or email.lower() == 'nan':
                continue
                
            raw_password = str(row.get("Mật Khẩu", "")).strip()
            role_str = str(row.get("Vai Trò", "")).strip().upper()
            majors_str = str(row.get("Ngành Phụ Trách", ""))
            
            if role_str not in [RoleEnum.STAFF_TRUONG.value, RoleEnum.STAFF_NGANH.value]:
                continue # Skip invalid roles
                
            role_enum = RoleEnum(role_str)
            
            # Process majors
            if role_enum == RoleEnum.STAFF_TRUONG:
                major_codes = []
            else:
                if majors_str and majors_str.lower() != 'nan':
                    major_codes = [m.strip() for m in majors_str.split(",") if m.strip()]
                else:
                    major_codes = []

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
                    profile.major_codes = major_codes
                else:
                    new_profile = StaffProfile(account_id=account.account_id, major_codes=major_codes)
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
                    major_codes=major_codes,
                    is_online=False,
                    current_load=0
                )
                db.add(new_profile)
                
            success_count += 1
            
        await db.commit()
        return {"message": "Import thành công", "imported_count": success_count}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi import dữ liệu: {str(e)}")

@router.get("/list")
async def list_staff(db: AsyncSession = Depends(get_db)):
    try:
        stmt = (
            select(Account, StaffProfile)
            .outerjoin(StaffProfile, Account.account_id == StaffProfile.account_id)
            .where(Account.role.in_([RoleEnum.STAFF_TRUONG, RoleEnum.STAFF_NGANH]))
        )
        result = await db.execute(stmt)
        
        response = []
        for account, profile in result.all():
            response.append({
                "id": str(account.account_id),
                "email": account.username,
                "role": account.role.value,
                "is_active": account.is_active,
                "major_codes": profile.major_codes if profile else []
            })
            
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách cán bộ: {str(e)}")

class StaffCreateRequest(BaseModel):
    email: str
    password: Optional[str] = "123"
    role: str
    major_codes: List[str] = []

@router.post("/create")
async def create_staff(
    req: StaffCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    email = req.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email không được để trống")
        
    role_str = req.role.strip().upper()
    if role_str not in [RoleEnum.STAFF_TRUONG.value, RoleEnum.STAFF_NGANH.value]:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
        
    role_enum = RoleEnum(role_str)
    
    if role_enum == RoleEnum.STAFF_TRUONG:
        major_codes = []
    else:
        major_codes = [m.strip() for m in req.major_codes if m.strip()]

    try:
        # Check if account exists
        stmt = select(Account).where(Account.username == email)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if account:
            # Update existing account
            if req.password:
                account.password_hash = get_password_hash(req.password)
            account.role = role_enum
            account.is_active = True
            
            # Check staff profile
            stmt_profile = select(StaffProfile).where(StaffProfile.account_id == account.account_id)
            res_profile = await db.execute(stmt_profile)
            profile = res_profile.scalar_one_or_none()
            
            if profile:
                profile.major_codes = major_codes
            else:
                new_profile = StaffProfile(account_id=account.account_id, major_codes=major_codes)
                db.add(new_profile)
        else:
            # Create new account
            raw_password = req.password if req.password else "123"
                
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
                major_codes=major_codes,
                is_online=False,
                current_load=0
            )
            db.add(new_profile)
            
        await db.commit()
        return {"message": "Thêm cán bộ thành công"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi thêm cán bộ: {str(e)}")

class StaffUpdateRequest(BaseModel):
    password: Optional[str] = None
    role: str
    major_codes: List[str] = []
    is_active: bool

@router.put("/update/{account_id}")
async def update_staff(
    account_id: str,
    req: StaffUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        acc_uuid = uuid.UUID(account_id)
        stmt = select(Account).where(Account.account_id == acc_uuid)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản cán bộ")
            
        role_str = req.role.strip().upper()
        if role_str not in [RoleEnum.STAFF_TRUONG.value, RoleEnum.STAFF_NGANH.value]:
            raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
            
        role_enum = RoleEnum(role_str)
        
        if req.password:
            account.password_hash = get_password_hash(req.password)
            
        account.role = role_enum
        account.is_active = req.is_active
        
        major_codes = [] if role_enum == RoleEnum.STAFF_TRUONG else [m.strip() for m in req.major_codes if m.strip()]
        
        stmt_profile = select(StaffProfile).where(StaffProfile.account_id == acc_uuid)
        res_profile = await db.execute(stmt_profile)
        profile = res_profile.scalar_one_or_none()
        
        if profile:
            profile.major_codes = major_codes
        else:
            new_profile = StaffProfile(account_id=acc_uuid, major_codes=major_codes)
            db.add(new_profile)
            
        await db.commit()
        return {"message": "Cập nhật cán bộ thành công"}
    except ValueError:
        raise HTTPException(status_code=400, detail="ID tài khoản không hợp lệ")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật cán bộ: {str(e)}")

@router.delete("/delete/{account_id}")
async def delete_staff(account_id: str, db: AsyncSession = Depends(get_db)):
    try:
        acc_uuid = uuid.UUID(account_id)
        account = await db.get(Account, acc_uuid)
        if not account:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản cán bộ")
            
        await db.delete(account)
        await db.commit()
        return {"message": "Xóa cán bộ thành công"}
    except ValueError:
        raise HTTPException(status_code=400, detail="ID tài khoản không hợp lệ")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa cán bộ: {str(e)}")

class BulkDeleteUUID(BaseModel):
    ids: List[str]

@router.post("/bulk-delete")
async def bulk_delete_staff(payload: BulkDeleteUUID, db: AsyncSession = Depends(get_db)):
    if not payload.ids:
        return {"message": "Không có cán bộ nào được chọn để xóa"}
        
    try:
        valid_uuids = [uuid.UUID(i) for i in payload.ids]
        stmt = delete(Account).where(Account.account_id.in_(valid_uuids))
        await db.execute(stmt)
        await db.commit()
        return {"message": f"Đã xóa thành công {len(valid_uuids)} cán bộ"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Một hoặc nhiều ID tài khoản không hợp lệ")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa hàng loạt: {str(e)}")
