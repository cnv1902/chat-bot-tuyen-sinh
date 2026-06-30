"""
core/cache_service.py
=====================
Load dữ liệu tuyển sinh từ PostgreSQL lên RAM khi startup.
JOIN sẵn: admission_plans + admission_codes + majors + institutes thành 1 bảng phẳng `_admission_cache: list[dict]`.
"""
import logging
from typing import Any
from sqlalchemy import select

from db.connection import AsyncSessionLocal
from db.models import AdmissionPlan, AdmissionCode, Major, Institute, AdmissionQuota

logger = logging.getLogger(__name__)

# Bảng ảo lưu trữ trên RAM (List of Dicts)
_admission_cache: list[dict[str, Any]] = []

# Mảng Alias hỗ trợ fuzzy matching
_MAJOR_ALIAS_MAP: dict[str, str] = {
    "cntt": "Công nghệ thông tin",
    "it": "Công nghệ thông tin",
    "attt": "An toàn thông tin",
    "kt": "Kinh tế",
    "qtkd": "Quản trị kinh doanh",
    "nna": "Ngôn ngữ Anh",
    "nn anh": "Ngôn ngữ Anh",
    "ktht": "Kỹ thuật hệ thống",
    "cnts": "Công nghệ thực phẩm",
    "sp": "Sư phạm",
    "gdth": "Giáo dục tiểu học",
    "gdmn": "Giáo dục mầm non",
}

async def load_admission_cache() -> None:
    """
    Load toàn bộ dữ liệu tuyển sinh từ Database vào bộ nhớ RAM.
    Được gọi 1 lần khi ứng dụng khởi động (lifespan trong main.py).
    Tránh lỗi N+1 query bằng một câu lệnh JOIN duy nhất.
    """
    global _admission_cache
    logger.info("[Cache] Bắt đầu load dữ liệu tuyển sinh lên RAM...")
    
    async with AsyncSessionLocal() as db:
        # Câu lệnh SELECT ... JOIN ... để lấy tất cả thông tin
        stmt = (
            select(
                AdmissionPlan.ma_xet_tuyen,
                AdmissionPlan.nam,
                AdmissionPlan.ma_phuong_thuc,
                AdmissionPlan.khoi,
                AdmissionPlan.diem_chuan,
                AdmissionPlan.hoc_ba_tbc_3_nam,
                AdmissionPlan.diem_tot_nghiep,
                AdmissionPlan.tbc_3_nam_ngoai_ngu,
                AdmissionPlan.hoc_luc_12,
                AdmissionPlan.nang_khieu,
                AdmissionPlan.mon_nhan_he_so,
                AdmissionPlan.tieng_anh,
                AdmissionPlan.ngoai_ngu,
                AdmissionPlan.he_so,
                AdmissionCode.program_name,
                Major.major_code,
                Major.major_name,
                Institute.institute_code,
                Institute.institute_name,
                AdmissionQuota.chi_tieu
            )
            .select_from(Major)
            .join(Institute, Major.institute_code == Institute.institute_code, isouter=True)
            .join(AdmissionCode, Major.major_code == AdmissionCode.major_code, isouter=True)
            .join(AdmissionPlan, AdmissionCode.admission_code == AdmissionPlan.ma_xet_tuyen, isouter=True)
            .join(AdmissionQuota, (AdmissionPlan.ma_xet_tuyen == AdmissionQuota.ma_xet_tuyen) & (AdmissionPlan.nam == AdmissionQuota.nam), isouter=True)
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        temp_cache = []
        for row in rows:
            temp_cache.append({
                "ma_xet_tuyen": row.ma_xet_tuyen,
                "ma_nganh": row.major_code,
                "nam": row.nam,
                "chi_tieu": row.chi_tieu,
                "ma_phuong_thuc": row.ma_phuong_thuc,
                "khoi": row.khoi,
                "diem_chuan": row.diem_chuan,
                "diem_hoc_ba": row.hoc_ba_tbc_3_nam,
                "diem_tot_nghiep": row.diem_tot_nghiep,
                "tbc_3_nam_ngoai_ngu": row.tbc_3_nam_ngoai_ngu,
                "hoc_luc_12": row.hoc_luc_12,
                "nang_khieu": row.nang_khieu,
                "mon_nhan_he_so": row.mon_nhan_he_so,
                "tieng_anh": row.tieng_anh,
                "ngoai_ngu": row.ngoai_ngu,
                "he_so": row.he_so,
                "program_name": row.program_name,
                "ten_chuong_trinh": row.program_name if row.program_name else "Đại trà",
                "major_code": row.major_code,
                "major_name": row.major_name,
                "ten_nganh": row.major_name,
                "institute_code": row.institute_code,
                "institute_name": row.institute_name,
            })
            
        _admission_cache = temp_cache
        logger.info(f"[Cache] Đã load thành công {len(_admission_cache)} bản ghi vào RAM.")

def get_admission_cache() -> list[dict[str, Any]]:
    """Trả về bảng ảo (dữ liệu đã lưu trên RAM)."""
    return _admission_cache

def normalize_and_map_alias(text: str) -> str:
    """Chuẩn hóa chuỗi và thay thế từ viết tắt thành tên đầy đủ."""
    if not text:
        return ""
    # Chuẩn hóa (lowercase, loại bỏ khoảng trắng thừa)
    normalized = " ".join(text.strip().lower().split())
    # Trả về alias nếu có trong dict
    return _MAJOR_ALIAS_MAP.get(normalized, normalized)
