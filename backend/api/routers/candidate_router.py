from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Optional
import pandas as pd
import io

from db.connection import get_db
from db.models import Account, CandidateProfile, RoleEnum

router = APIRouter(
    prefix="/api/candidates",
    tags=["Candidates"]
)

@router.get("/list")
async def list_candidates(
    search: Optional[str] = Query(None, description="Tìm kiếm theo email hoặc họ tên"),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Account, CandidateProfile).join(
            CandidateProfile, Account.account_id == CandidateProfile.account_id, isouter=True
        ).where(Account.role == RoleEnum.CANDIDATE)
        
        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                or_(
                    CandidateProfile.email.ilike(search_term),
                    CandidateProfile.full_name.ilike(search_term),
                    Account.username.ilike(search_term)
                )
            )
            
        result = await db.execute(stmt)
        rows = result.all()
        
        candidates = []
        for account, profile in rows:
            candidates.append({
                "account_id": str(account.account_id),
                "email": profile.email if profile and profile.email else account.username,
                "full_name": profile.full_name if profile else None,
                "phone_number": profile.phone_number if profile else None,
                "interested_majors": profile.interested_majors if profile else None,
                "is_active": account.is_active
            })
            
        return candidates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách thí sinh: {str(e)}")

@router.get("/export")
async def export_candidates(db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Account, CandidateProfile).join(
            CandidateProfile, Account.account_id == CandidateProfile.account_id, isouter=True
        ).where(Account.role == RoleEnum.CANDIDATE)
        
        result = await db.execute(stmt)
        rows = result.all()
        
        data = []
        for account, profile in rows:
            data.append({
                "Email": profile.email if profile and profile.email else account.username,
                "Họ Tên": profile.full_name if profile else "",
                "Số Điện Thoại": profile.phone_number if profile else "",
                "Ngành Quan Tâm": profile.interested_majors if profile else "",
                "Trạng Thái": "Hoạt động" if account.is_active else "Bị khóa"
            })
            
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Thi_Sinh')
            
        output.seek(0)
        
        headers = {
            'Content-Disposition': 'attachment; filename="Danh_Sach_Thi_Sinh.xlsx"'
        }
        
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xuất danh sách thí sinh: {str(e)}")
