from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, constr
from typing import List
import logging

from db.connection import get_db
from db.models import AdmissionCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admissions", tags=["admissions"])

# -------------------------------------------------------------------------
# DTOs (Data Transfer Objects)
# -------------------------------------------------------------------------
class AdmissionResponseDTO(BaseModel):
    admissionCode: str
    majorCode: str
    programName: str

    class Config:
        orm_mode = True

class AdmissionImportDTO(BaseModel):
    admissionCode: str = Field(..., min_length=1, description="Mã xét tuyển")
    majorCode: str = Field(..., min_length=1, description="Mã Ngành")
    programName: str = Field(..., min_length=1, description="Tên Chương Trình")

class ImportResultDTO(BaseModel):
    success: int
    failed: int
    errors: List[str]

class AdmissionUpdateDTO(BaseModel):
    majorCode: str = Field(..., min_length=1, description="Mã Ngành")
    programName: str = Field(..., min_length=1, description="Tên Chương Trình")

class BulkDeleteAdmissionDTO(BaseModel):
    ids: List[str]

# -------------------------------------------------------------------------
# Service Layer / Logic
# -------------------------------------------------------------------------
async def get_all_admissions(db: AsyncSession) -> List[AdmissionCode]:
    stmt = select(AdmissionCode)
    result = await db.execute(stmt)
    return result.scalars().all()

async def upsert_admissions_from_dto(db: AsyncSession, payload: List[AdmissionImportDTO]) -> ImportResultDTO:
    if not payload:
        raise HTTPException(status_code=400, detail="Danh sách import trống.")

    success_count = 0
    fail_count = 0
    errors = []

    try:
        # Lấy toàn bộ mã hiện có trong DB để đối chiếu (tránh query từng record)
        stmt = select(AdmissionCode)
        result = await db.execute(stmt)
        existing_records = {r.admission_code: r for r in result.scalars().all()}

        for item in payload:
            try:
                # Mapping từ DTO sang Entity (Bảo toàn cấu trúc Entity hiện tại)
                if item.admissionCode in existing_records:
                    # Update (Upsert logic)
                    record = existing_records[item.admissionCode]
                    record.major_code = item.majorCode
                    record.program_name = item.programName
                else:
                    # Insert
                    new_record = AdmissionCode(
                        admission_code=item.admissionCode,
                        major_code=item.majorCode,
                        program_name=item.programName
                    )
                    db.add(new_record)
                    # Cập nhật dictionary cho các phần tử sau nếu có mã trùng trong cùng batch
                    existing_records[item.admissionCode] = new_record
                
                success_count += 1
            except Exception as item_ex:
                fail_count += 1
                errors.append(f"Lỗi tại mã {item.admissionCode}: {str(item_ex)}")

        # Sử dụng Transaction: Commit toàn bộ nếu không có lỗi hệ thống, 
        # (Lỗi validate/parse đã bị catch riêng cho từng item)
        await db.commit()

    except Exception as ex:
        # Rollback toàn bộ nếu có lỗi ở tầng Database/Transaction
        await db.rollback()
        logger.error(f"[AdmissionCode] Transaction rollback do lỗi: {str(ex)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Quá trình import thất bại, đã rollback toàn bộ dữ liệu. Lỗi: {str(ex)}"
        )

    return ImportResultDTO(
        success=success_count,
        failed=fail_count,
        errors=errors
    )

# -------------------------------------------------------------------------
# Controller / Router Endpoints
# -------------------------------------------------------------------------
@router.get("", response_model=List[AdmissionResponseDTO])
async def get_admissions_api(db: AsyncSession = Depends(get_db)):
    """
    1. GET /api/admissions
    - Lấy danh sách toàn bộ mã xét tuyển
    """
    records = await get_all_admissions(db)
    # Mapping Entity sang Response DTO
    return [
        AdmissionResponseDTO(
            admissionCode=r.admission_code,
            majorCode=r.major_code,
            programName=r.program_name
        )
        for r in records
    ]

@router.post("/import", response_model=ImportResultDTO)
async def import_admissions_api(payload: List[AdmissionImportDTO], db: AsyncSession = Depends(get_db)):
    """
    2. POST /api/admissions/import
    - Nhận array JSON (các AdmissionImportDTO)
    - Validate và import (Upsert) vào bảng AdmissionCode với Transaction
    """
    return await upsert_admissions_from_dto(db, payload)

@router.put("/{admission_code}")
async def update_admission_code(admission_code: str, payload: AdmissionUpdateDTO, db: AsyncSession = Depends(get_db)):
    record = await db.get(AdmissionCode, admission_code)
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã xét tuyển này")
    
    record.major_code = payload.majorCode
    record.program_name = payload.programName
    await db.commit()
    return {"message": "Cập nhật thành công"}

@router.delete("/{admission_code}")
async def delete_admission_code(admission_code: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(AdmissionCode, admission_code)
    if not record:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã xét tuyển này")
    
    await db.delete(record)
    await db.commit()
    return {"message": "Xóa thành công"}

@router.post("/bulk-delete")
async def bulk_delete_admission_codes(payload: BulkDeleteAdmissionDTO, db: AsyncSession = Depends(get_db)):
    if not payload.ids:
        return {"message": "Không có mã nào được chọn"}
        
    from sqlalchemy import delete
    stmt = delete(AdmissionCode).where(AdmissionCode.admission_code.in_(payload.ids))
    await db.execute(stmt)
    await db.commit()
    return {"message": f"Đã xóa {len(payload.ids)} bản ghi"}
