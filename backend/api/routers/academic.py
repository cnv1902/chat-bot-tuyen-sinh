import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd

from db.connection import get_db
from db.models import Institute, Major

router = APIRouter(prefix="/api/academic", tags=["academic"])

@router.post("/import-institutes")
async def import_institutes(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .xlsx")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp Excel: {str(e)}")
    
    if "Mã Trường/Viện" not in df.columns or "Tên Trường/Viện" not in df.columns:
        raise HTTPException(status_code=400, detail="Tệp không đúng định dạng. Yêu cầu cột: Mã Trường/Viện, Tên Trường/Viện")

    count = 0
    for _, row in df.iterrows():
        code = str(row.get("Mã Trường/Viện", "")).strip()
        name = str(row.get("Tên Trường/Viện", "")).strip()
        
        if not code or code == 'nan':
            continue
            
        # Kiểm tra tồn tại
        stmt = select(Institute).where(Institute.institute_code == code)
        result = await db.execute(stmt)
        institute = result.scalar_one_or_none()
        
        if institute:
            institute.institute_name = name
        else:
            institute = Institute(institute_code=code, institute_name=name)
            db.add(institute)
        count += 1
        
    await db.commit()
    return {"message": f"Đã nhập thành công {count} Trường/Viện."}

@router.post("/import-majors")
async def import_majors(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .xlsx")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp Excel: {str(e)}")
    
    required_cols = ["Mã Ngành", "Mã Trường/Viện", "Tên Ngành"]
    if not all(col in df.columns for col in required_cols):
        raise HTTPException(status_code=400, detail=f"Tệp không đúng định dạng. Yêu cầu các cột: {', '.join(required_cols)}")

    count = 0
    for _, row in df.iterrows():
        m_code = str(row.get("Mã Ngành", "")).strip()
        i_code = str(row.get("Mã Trường/Viện", "")).strip()
        m_name = str(row.get("Tên Ngành", "")).strip()
        
        if not m_code or m_code == 'nan' or not i_code or i_code == 'nan':
            continue
            
        # Kiểm tra xem Institute đã tồn tại chưa, nếu chưa thì tự động tạo mới để tránh lỗi Foreign Key
        stmt_inst = select(Institute).where(Institute.institute_code == i_code)
        inst_exists = (await db.execute(stmt_inst)).scalar_one_or_none()
        if not inst_exists:
            new_inst = Institute(institute_code=i_code, institute_name=i_code)
            db.add(new_inst)
            await db.flush() # Commit nhẹ để có institute_code hợp lệ cho Major

        # Kiem tra tồn tại Major
        stmt = select(Major).where(Major.major_code == m_code)
        result = await db.execute(stmt)
        major = result.scalar_one_or_none()
        
        if major:
            major.institute_code = i_code
            major.major_name = m_name
        else:
            major = Major(
                major_code=m_code,
                institute_code=i_code,
                major_name=m_name,
                training_program=None,
                subject_combinations=[]
            )
            db.add(major)
        count += 1
        
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi khi lưu dữ liệu, có thể do Mã Trường/Viện không tồn tại: {str(e)}")
        
    return {"message": f"Đã nhập thành công {count} Ngành đào tạo."}

@router.get("/tree")
async def get_academic_tree(db: AsyncSession = Depends(get_db)):
    """Trả về cấu trúc cây phân cấp Trường/Viện -> Ngành."""
    stmt = select(Institute)
    result = await db.execute(stmt)
    institutes = result.scalars().all()
    
    stmt_majors = select(Major)
    result_majors = await db.execute(stmt_majors)
    all_majors = result_majors.scalars().all()
    
    # Gom nhóm majors theo institute_code
    majors_dict = {}
    for m in all_majors:
        if m.institute_code not in majors_dict:
            majors_dict[m.institute_code] = []
        majors_dict[m.institute_code].append({
            "major_code": m.major_code,
            "major_name": m.major_name
        })
        
    tree = []
    for inst in institutes:
        tree.append({
            "institute_code": inst.institute_code,
            "institute_name": inst.institute_name,
            "majors": majors_dict.get(inst.institute_code, [])
        })
        
    return tree

class InstituteUpdate(BaseModel):
    institute_name: str

class MajorUpdate(BaseModel):
    major_name: str
    institute_code: str

class BulkDeleteRequest(BaseModel):
    institute_codes: List[str] = []
    major_codes: List[str] = []

@router.put("/institutes/{code}")
async def update_institute(code: str, data: InstituteUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Institute).where(Institute.institute_code == code)
    result = await db.execute(stmt)
    institute = result.scalar_one_or_none()
    
    if not institute:
        raise HTTPException(status_code=404, detail="Không tìm thấy Trường/Viện")
        
    institute.institute_name = data.institute_name
    await db.commit()
    return {"message": "Cập nhật thành công"}

@router.delete("/institutes/{code}")
async def delete_institute(code: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Institute).where(Institute.institute_code == code)
    result = await db.execute(stmt)
    institute = result.scalar_one_or_none()
    
    if not institute:
        raise HTTPException(status_code=404, detail="Không tìm thấy Trường/Viện")
        
    await db.delete(institute)
    await db.commit()
    return {"message": "Xóa thành công"}

@router.put("/majors/{code}")
async def update_major(code: str, data: MajorUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Major).where(Major.major_code == code)
    result = await db.execute(stmt)
    major = result.scalar_one_or_none()
    
    if not major:
        raise HTTPException(status_code=404, detail="Không tìm thấy Ngành")
        
    major.major_name = data.major_name
    major.institute_code = data.institute_code
    
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Mã Trường/Viện không hợp lệ")
        
    return {"message": "Cập nhật thành công"}

@router.delete("/majors/{code}")
async def delete_major(code: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Major).where(Major.major_code == code)
    result = await db.execute(stmt)
    major = result.scalar_one_or_none()
    
    if not major:
        raise HTTPException(status_code=404, detail="Không tìm thấy Ngành")
        
    await db.delete(major)
    await db.commit()
    return {"message": "Xóa thành công"}

@router.post("/bulk-delete")
async def bulk_delete_academic(data: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    deleted_inst = 0
    deleted_major = 0
    
    # Xóa ngành trước
    if data.major_codes:
        stmt = select(Major).where(Major.major_code.in_(data.major_codes))
        result = await db.execute(stmt)
        majors = result.scalars().all()
        for m in majors:
            await db.delete(m)
            deleted_major += 1
            
    # Xóa trường
    if data.institute_codes:
        stmt = select(Institute).where(Institute.institute_code.in_(data.institute_codes))
        result = await db.execute(stmt)
        institutes = result.scalars().all()
        for i in institutes:
            await db.delete(i)
            deleted_inst += 1
            
    await db.commit()
    return {"message": f"Đã xóa {deleted_inst} Trường/Viện và {deleted_major} Ngành"}
