import io
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import pandas as pd
import logging

logger = logging.getLogger(__name__)

from db.connection import get_db
from db.models import Major, SubjectCombination, AdmissionMethod, AdmissionPlan

router = APIRouter(prefix="/api/admission", tags=["admission"])

@router.post("/import-combinations")
async def import_combinations(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    logger.info(f"[Admission] Bắt đầu xử lý import Tổ hợp môn từ file: {file.filename}")
    if not file.filename.endswith('.xlsx'):
        logger.warning(f"[Admission] Import thất bại: Định dạng tệp không hợp lệ ({file.filename})")
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .xlsx")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp Excel: {str(e)}")
    
    required_cols = ["Mã Tổ Hợp", "Các Môn"]
    if not all(col in df.columns for col in required_cols):
        raise HTTPException(status_code=400, detail=f"Tệp không đúng định dạng. Yêu cầu: {', '.join(required_cols)}")

    count = 0
    for _, row in df.iterrows():
        code = str(row.get("Mã Tổ Hợp", "")).strip()
        subjects = str(row.get("Các Môn", "")).strip()
        
        if not code or code == 'nan':
            continue
            
        stmt = select(SubjectCombination).where(SubjectCombination.combo_code == code)
        result = await db.execute(stmt)
        combo = result.scalar_one_or_none()
        
        if combo:
            combo.subjects = subjects
        else:
            combo = SubjectCombination(combo_code=code, subjects=subjects)
            db.add(combo)
        count += 1
        
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[Admission] Lỗi lưu dữ liệu Tổ hợp môn: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Lỗi lưu dữ liệu: {str(e)}")
        
    logger.info(f"[Admission] Đã import thành công {count} Tổ hợp môn.")
    return {"message": f"Đã nạp thành công {count} Tổ hợp môn."}

@router.post("/import-methods")
async def import_methods(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    logger.info(f"[Admission] Bắt đầu xử lý import Phương thức từ file: {file.filename}")
    if not file.filename.endswith('.xlsx'):
        logger.warning(f"[Admission] Import thất bại: Định dạng tệp không hợp lệ ({file.filename})")
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .xlsx")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        logger.error(f"[Admission] Lỗi khi đọc tệp Excel Phương thức: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp Excel: {str(e)}")
    
    required_cols = ["Năm", "Mã Phương Thức", "Tên Phương Thức"]
    if not all(col in df.columns for col in required_cols):
        logger.warning(f"[Admission] Định dạng tệp không hợp lệ: {file.filename}")
        raise HTTPException(status_code=400, detail=f"Tệp không đúng định dạng. Yêu cầu: {', '.join(required_cols)}")

    count = 0
    for _, row in df.iterrows():
        year_raw = row.get("Năm", None)
        method_code = str(row.get("Mã Phương Thức", "")).strip()
        method_name = str(row.get("Tên Phương Thức", "")).strip()
        
        if not method_code or method_code == 'nan' or pd.isna(year_raw):
            continue
            
        try:
            year = int(year_raw)
        except ValueError:
            continue
            
        stmt = select(AdmissionMethod).where(
            AdmissionMethod.year == year, 
            AdmissionMethod.method_code == method_code
        )
        result = await db.execute(stmt)
        method = result.scalar_one_or_none()
        
        if method:
            method.method_name = method_name
        else:
            method = AdmissionMethod(year=year, method_code=method_code, method_name=method_name)
            db.add(method)
        count += 1
        
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[Admission] Lỗi lưu dữ liệu Phương thức: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Lỗi lưu dữ liệu: {str(e)}")
        
    logger.info(f"[Admission] Đã import thành công {count} Phương thức xét tuyển.")
    return {"message": f"Đã nạp thành công {count} Phương thức xét tuyển."}

@router.post("/import-plans")
async def import_plans(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    logger.info(f"[Admission] Bắt đầu xử lý import Đề án từ file: {file.filename}")
    if not file.filename.endswith('.xlsx'):
        logger.warning(f"[Admission] Import thất bại: Định dạng tệp không hợp lệ ({file.filename})")
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận tệp định dạng .xlsx")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        logger.error(f"[Admission] Lỗi khi đọc tệp Excel Đề án: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp Excel: {str(e)}")
    
    required_cols = ["Năm", "Mã Ngành", "Mã Phương Thức", "Mã Tổ Hợp", "Chỉ Tiêu"]
    if not all(col in df.columns for col in required_cols):
        logger.warning(f"[Admission] Định dạng tệp không hợp lệ: {file.filename}")
        raise HTTPException(status_code=400, detail=f"Tệp không đúng định dạng. Yêu cầu các cột: {', '.join(required_cols)}")

    has_quota = "Chỉ Tiêu" in df.columns

    inserted = 0
    updated = 0
    for _, row in df.iterrows():
        year_raw = row.get("Năm", None)
        major_code = str(row.get("Mã Ngành", "")).strip()
        methods_raw = str(row.get("Mã Phương Thức", "")).strip()
        combos_raw = str(row.get("Mã Tổ Hợp", "")).strip()
        
        if pd.isna(year_raw) or not major_code or major_code == 'nan' or not methods_raw or methods_raw == 'nan':
            continue
            
        try:
            year = int(float(year_raw))
        except ValueError:
            continue
            
        if combos_raw and combos_raw.lower() != 'nan':
            combo_list = [c.strip() for c in combos_raw.split(',') if c.strip()]
        else:
            combo_list = []
            
        method_list = [m.strip() for m in methods_raw.split(',') if m.strip()]
            
        target_quota = None
        if has_quota:
            q_val = row.get("Chỉ Tiêu", None)
            if not pd.isna(q_val):
                try:
                    target_quota = int(q_val)
                except ValueError:
                    pass

        # Upsert logic based on year and major_code ONLY
        stmt = select(AdmissionPlan).where(
            AdmissionPlan.year == year,
            AdmissionPlan.major_code == major_code
        )
        result = await db.execute(stmt)
        plan = result.scalar_one_or_none()
        
        if plan:
            plan.methods = method_list
            plan.combinations = combo_list
            if target_quota is not None:
                plan.target_quota = target_quota
            updated += 1
        else:
            new_plan = AdmissionPlan(
                year=year,
                major_code=major_code,
                methods=method_list,
                combinations=combo_list,
                target_quota=target_quota
            )
            db.add(new_plan)
            inserted += 1
        
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[Admission] Lỗi lưu dữ liệu Đề án: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Lỗi lưu dữ liệu: {str(e)}")
        
    logger.info(f"[Admission] Đã import thành công {inserted + updated} Đề án xét tuyển (Mới: {inserted}, Cập nhật: {updated}).")
    return {"message": f"Đã nạp thành công {inserted + updated} Đề án xét tuyển."}

@router.get("/plans")
async def get_admission_plans(
    year: int = Query(None, description="Năm tuyển sinh"),
    major_code: Optional[str] = Query(None, description="Lọc theo Mã Ngành"),
    db: AsyncSession = Depends(get_db)
):
    if not year:
        stmt_max = select(AdmissionPlan.year).order_by(AdmissionPlan.year.desc()).limit(1)
        res_year = await db.execute(stmt_max)
        year = res_year.scalar() or 2026
        
    stmt = (
        select(AdmissionPlan, Major)
        .join(Major, AdmissionPlan.major_code == Major.major_code)
        .where(AdmissionPlan.year == year)
    )
    
    if major_code:
        stmt = stmt.where(Major.major_code.ilike(f"%{major_code}%"))
        
    result = await db.execute(stmt)
    rows = result.all()
    
    # Lấy thông tin Phương thức để map tên
    stmt_methods = select(AdmissionMethod).where(AdmissionMethod.year == year)
    res_methods = await db.execute(stmt_methods)
    methods_dict = {m.method_code: m.method_name for m in res_methods.scalars().all()}
    
    # Lấy thông tin Tổ hợp để map tên môn
    stmt_combos = select(SubjectCombination)
    res_combos = await db.execute(stmt_combos)
    combos_dict = {c.combo_code: c.subjects for c in res_combos.scalars().all()}
    
    response = []
    for plan, major in rows:
        plan_methods = []
        for mc in plan.methods:
            plan_methods.append({
                "code": mc,
                "name": methods_dict.get(mc, "Không xác định")
            })
            
        plan_combos = []
        for cc in plan.combinations:
            plan_combos.append({
                "code": cc,
                "subjects": combos_dict.get(cc, "Không xác định")
            })
            
        response.append({
            "id": plan.id,
            "year": plan.year,
            "major_code": plan.major_code,
            "major_name": major.major_name,
            "methods": plan_methods,
            "combinations": plan_combos,
            "target_quota": plan.target_quota
        })
        
    return response

@router.get("/methods")
async def get_admission_methods(
    year: int = Query(None, description="Năm tuyển sinh"),
    db: AsyncSession = Depends(get_db)
):
    if not year:
        stmt_max = select(AdmissionMethod.year).order_by(AdmissionMethod.year.desc()).limit(1)
        res_year = await db.execute(stmt_max)
        year = res_year.scalar() or 2026
        
    stmt = select(AdmissionMethod).where(AdmissionMethod.year == year)
    result = await db.execute(stmt)
    methods = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "year": m.year,
            "method_code": m.method_code,
            "method_name": m.method_name
        }
        for m in methods
    ]

@router.get("/combinations")
async def get_subject_combinations(
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SubjectCombination)
    result = await db.execute(stmt)
    combinations = result.scalars().all()
    
    return [
        {
            "id": c.combo_code,
            "combo_code": c.combo_code,
            "subjects": c.subjects
        }
        for c in combinations
    ]
