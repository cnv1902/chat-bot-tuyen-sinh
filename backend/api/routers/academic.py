import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
            
        # Kiem tra tồn tại
        stmt = select(Major).where(Major.major_code == m_code)
        result = await db.execute(stmt)
        major = result.scalar_one_or_none()
        
        if major:
            major.institute_code = i_code
            major.major_name = m_name
            # Có thể gán None cho các cột dư thừa nếu muốn xóa sạch dữ liệu cũ
            major.training_program = None
            major.subject_combinations = []
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
