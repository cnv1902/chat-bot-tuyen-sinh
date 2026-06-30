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
from db.models import Major, SubjectCombination, AdmissionMethod, AdmissionPlan, AdmissionCode, AdmissionQuota

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
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file định dạng Excel hoặc CSV")
    
    try:
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp: {str(e)}")
    
    # Chuẩn hóa tên cột để mapping cho dễ (chuyển về lowercase, strip khoảng trắng)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Định nghĩa map từ cột tiếng Việt sang trường DB
    col_map = {
        "mã xét tuyển": "ma_xet_tuyen",
        "mã ngành": "ma_nganh",
        "năm": "nam",
        "mã phương thức": "ma_phuong_thuc",
        "khối": "khoi",
        "điểm chuẩn": "diem_chuan",
        "học bạ trung bình chung 3 năm": "hoc_ba_tbc_3_nam",
        "điểm tốt nghiệp": "diem_tot_nghiep",
        "trung bình chung 3 năm ngoại ngữ": "tbc_3_nam_ngoai_ngu",
        "học lực 12": "hoc_luc_12",
        "năng khiếu": "nang_khieu",
        "môn nhân hệ số": "mon_nhan_he_so",
        "tiếng anh": "tieng_anh",
        "ngoại ngữ": "ngoai_ngu",
        "hệ số": "he_so"
    }
    
    # Tạo dictionary index cột để truy xuất
    actual_cols = {}
    for raw_col in df.columns:
        for vn_name, db_name in col_map.items():
            if vn_name == raw_col:
                actual_cols[db_name] = raw_col
                break
                
    if "ma_xet_tuyen" not in actual_cols:
        raise HTTPException(status_code=400, detail="Tệp không có cột 'Mã xét tuyển'.")

    # Thay thế NaN bằng None
    df = df.where(pd.notnull(df), None)

    records = []
    for _, row in df.iterrows():
        # Lấy ma_xet_tuyen
        ma_xt = str(row.get(actual_cols.get("ma_xet_tuyen", "")))
        if ma_xt == 'None' or ma_xt.strip() == '':
            continue
            
        def get_val(db_name):
            if db_name not in actual_cols:
                return None
            val = row.get(actual_cols[db_name])
            if val is None or str(val).strip() == 'None' or str(val).strip() == 'nan':
                return None
            return str(val).strip()
            
        def get_int(db_name):
            val = get_val(db_name)
            if not val:
                return None
            try:
                # Có thể file excel parse năm thành 2024.0 -> float -> int
                return int(float(val))
            except:
                return None

        record = AdmissionPlan(
            ma_xet_tuyen=get_val("ma_xet_tuyen"),
            ma_nganh=get_val("ma_nganh"),
            nam=get_int("nam"),
            ma_phuong_thuc=get_val("ma_phuong_thuc"),
            khoi=get_val("khoi"),
            diem_chuan=get_val("diem_chuan"),
            hoc_ba_tbc_3_nam=get_val("hoc_ba_tbc_3_nam"),
            diem_tot_nghiep=get_val("diem_tot_nghiep"),
            tbc_3_nam_ngoai_ngu=get_val("tbc_3_nam_ngoai_ngu"),
            hoc_luc_12=get_val("hoc_luc_12"),
            nang_khieu=get_val("nang_khieu"),
            mon_nhan_he_so=get_val("mon_nhan_he_so"),
            tieng_anh=get_val("tieng_anh"),
            ngoai_ngu=get_val("ngoai_ngu"),
            he_so=get_val("he_so")
        )
        records.append(record)
        
    if not records:
        raise HTTPException(status_code=400, detail="Không tìm thấy dòng dữ liệu nào hợp lệ.")
        
    db.add_all(records)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi lưu Database: {str(e)}")
        
    return {"message": f"Đã nhập thành công {len(records)} đề án tuyển sinh."}

@router.post("/import-quotas")
async def import_quotas(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    logger.info(f"[Admission] Bắt đầu xử lý import Chỉ tiêu từ file: {file.filename}")
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file định dạng Excel hoặc CSV")
    
    try:
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi đọc tệp: {str(e)}")
        
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    col_map = {
        "mã xét tuyển": "ma_xet_tuyen",
        "năm": "nam",
        "chỉ tiêu": "chi_tieu"
    }
    
    actual_cols = {}
    for raw_col in df.columns:
        for vn_name, db_name in col_map.items():
            if vn_name == raw_col:
                actual_cols[db_name] = raw_col
                break
                
    if "ma_xet_tuyen" not in actual_cols or "nam" not in actual_cols or "chi_tieu" not in actual_cols:
        raise HTTPException(status_code=400, detail="Tệp không đủ 3 cột: Năm, Mã xét tuyển, Chỉ tiêu.")

    df = df.where(pd.notnull(df), None)

    count = 0
    for _, row in df.iterrows():
        ma_xt = str(row.get(actual_cols.get("ma_xet_tuyen", ""))).strip()
        nam_raw = row.get(actual_cols.get("nam"))
        chi_tieu_raw = row.get(actual_cols.get("chi_tieu"))
        
        if not ma_xt or ma_xt == 'None' or ma_xt == 'nan':
            continue
            
        try:
            nam = int(float(nam_raw))
            chi_tieu = int(float(chi_tieu_raw))
        except (ValueError, TypeError):
            continue
            
        stmt = select(AdmissionQuota).where(
            AdmissionQuota.nam == nam, 
            AdmissionQuota.ma_xet_tuyen == ma_xt
        )
        result = await db.execute(stmt)
        quota = result.scalar_one_or_none()
        
        if quota:
            quota.chi_tieu = chi_tieu
        else:
            quota = AdmissionQuota(nam=nam, ma_xet_tuyen=ma_xt, chi_tieu=chi_tieu)
            db.add(quota)
        count += 1
        
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Lỗi lưu Database: {str(e)}")
        
    return {"message": f"Đã nạp thành công {count} chỉ tiêu."}

@router.get("/quotas")
async def get_admission_quotas(db: AsyncSession = Depends(get_db)):
    stmt = select(AdmissionQuota).order_by(AdmissionQuota.nam.desc(), AdmissionQuota.ma_xet_tuyen)
    result = await db.execute(stmt)
    quotas = result.scalars().all()
    
    return [
        {
            "id": q.id,
            "nam": q.nam,
            "ma_xet_tuyen": q.ma_xet_tuyen,
            "chi_tieu": q.chi_tieu
        }
        for q in quotas
    ]


@router.get("/plans")
async def get_admission_plans(
    page: int = Query(1, ge=1),
    size: int = Query(5000, ge=1),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(AdmissionPlan, AdmissionCode.program_name, Major.major_name, AdmissionQuota.chi_tieu)
        .outerjoin(AdmissionCode, AdmissionPlan.ma_xet_tuyen == AdmissionCode.admission_code)
        .outerjoin(Major, AdmissionPlan.ma_nganh == Major.major_code)
        .outerjoin(AdmissionQuota, (AdmissionPlan.ma_xet_tuyen == AdmissionQuota.ma_xet_tuyen) & (AdmissionPlan.nam == AdmissionQuota.nam))
        .order_by(AdmissionPlan.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    data = []
    for plan, program_name, major_name, chi_tieu in rows:
        data.append({
            "id": plan.id,
            "maXetTuyen": plan.ma_xet_tuyen,
            "maNganh": plan.ma_nganh,
            "nam": plan.nam,
            "maPhuongThuc": plan.ma_phuong_thuc,
            "khoi": plan.khoi,
            "diemChuan": plan.diem_chuan,
            "hocBaTrungBinhChung3Nam": plan.hoc_ba_tbc_3_nam,
            "diemTotNghiep": plan.diem_tot_nghiep,
            "trungBinhChung3NamNgoaiNgu": plan.tbc_3_nam_ngoai_ngu,
            "hocLuc12": plan.hoc_luc_12,
            "nangKhieu": plan.nang_khieu,
            "monNhanHeSo": plan.mon_nhan_he_so,
            "tiengAnh": plan.tieng_anh,
            "ngoaiNgu": plan.ngoai_ngu,
            "heSo": plan.he_so,
            "programName": program_name,
            "majorName": major_name,
            "chiTieu": chi_tieu
        })
        
    # Get total count (optional, but good for pagination if needed)
    from sqlalchemy import func
    count_stmt = select(func.count(AdmissionPlan.id))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    return {
        "data": data,
        "total": total,
        "page": page,
        "size": size
    }


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
