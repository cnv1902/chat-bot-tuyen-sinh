from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import List, Optional

from db.connection import get_db
from db.models import SubjectCombination, AdmissionMethod, AdmissionPlan, AdmissionQuota
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admission_crud", tags=["admission_crud"])

class MethodCreate(BaseModel):
    year: int
    method_code: str
    method_name: str

class ComboCreate(BaseModel):
    combo_code: str
    subjects: str

class PlanCreate(BaseModel):
    ma_xet_tuyen: Optional[str] = None
    ma_nganh: Optional[str] = None
    nam: Optional[int] = None
    ma_phuong_thuc: Optional[str] = None
    khoi: Optional[str] = None
    diem_chuan: Optional[str] = None
    hoc_ba_tbc_3_nam: Optional[str] = None
    diem_tot_nghiep: Optional[str] = None
    tbc_3_nam_ngoai_ngu: Optional[str] = None
    hoc_luc_12: Optional[str] = None
    nang_khieu: Optional[str] = None
    mon_nhan_he_so: Optional[str] = None
    tieng_anh: Optional[str] = None
    ngoai_ngu: Optional[str] = None
    he_so: Optional[str] = None

class QuotaCreate(BaseModel):
    nam: Optional[int] = None
    ma_xet_tuyen: Optional[str] = None
    chi_tieu: Optional[int] = None

class BulkDeleteInt(BaseModel):
    ids: List[int]

class BulkDeleteStr(BaseModel):
    ids: List[str]

# ---- METHODS ----
@router.post("/methods")
async def create_method(item: MethodCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu thêm Phương thức: {item.method_code} ({item.year})")
    stmt = select(AdmissionMethod).where(AdmissionMethod.method_code == item.method_code, AdmissionMethod.year == item.year)
    if (await db.execute(stmt)).scalar_one_or_none():
        logger.warning(f"[CRUD] Thêm Phương thức thất bại: Mã {item.method_code} đã tồn tại")
        raise HTTPException(400, "Mã phương thức đã tồn tại trong năm này")
    
    new_method = AdmissionMethod(year=item.year, method_code=item.method_code, method_name=item.method_name)
    db.add(new_method)
    await db.commit()
    logger.info(f"[CRUD] Thêm Phương thức thành công: {item.method_code}")
    return {"message": "Thêm thành công"}

@router.put("/methods/{id}")
async def update_method(id: int, item: MethodCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu cập nhật Phương thức ID: {id}")
    method = await db.get(AdmissionMethod, id)
    if not method: 
        logger.warning(f"[CRUD] Cập nhật Phương thức thất bại: Không tìm thấy ID {id}")
        raise HTTPException(404, "Không tìm thấy")
    
    method.year = item.year
    method.method_code = item.method_code
    method.method_name = item.method_name
    await db.commit()
    logger.info(f"[CRUD] Cập nhật Phương thức thành công: ID {id}")
    return {"message": "Cập nhật thành công"}

@router.delete("/methods/{id}")
async def delete_method(id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa Phương thức ID: {id}")
    method = await db.get(AdmissionMethod, id)
    if not method: 
        logger.warning(f"[CRUD] Xóa Phương thức thất bại: Không tìm thấy ID {id}")
        raise HTTPException(404, "Không tìm thấy")
    await db.delete(method)
    await db.commit()
    logger.info(f"[CRUD] Xóa Phương thức thành công: ID {id}")
    return {"message": "Xóa thành công"}

@router.post("/methods/bulk-delete")
async def bulk_delete_methods(payload: BulkDeleteInt, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa hàng loạt Phương thức: {len(payload.ids)} mục")
    if not payload.ids:
        return {"message": "Không có mục nào được chọn để xóa"}
    stmt = delete(AdmissionMethod).where(AdmissionMethod.id.in_(payload.ids))
    await db.execute(stmt)
    await db.commit()
    logger.info(f"[CRUD] Xóa hàng loạt Phương thức thành công")
    return {"message": f"Đã xóa thành công {len(payload.ids)} mục"}


# ---- COMBINATIONS ----
@router.post("/combinations")
async def create_combo(item: ComboCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu thêm Tổ hợp: {item.combo_code}")
    stmt = select(SubjectCombination).where(SubjectCombination.combo_code == item.combo_code)
    if (await db.execute(stmt)).scalar_one_or_none():
        logger.warning(f"[CRUD] Thêm Tổ hợp thất bại: Mã {item.combo_code} đã tồn tại")
        raise HTTPException(400, "Mã tổ hợp đã tồn tại")
        
    new_combo = SubjectCombination(combo_code=item.combo_code, subjects=item.subjects)
    db.add(new_combo)
    await db.commit()
    logger.info(f"[CRUD] Thêm Tổ hợp thành công: {item.combo_code}")
    return {"message": "Thêm thành công"}

@router.put("/combinations/{combo_code}")
async def update_combo(combo_code: str, item: ComboCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu cập nhật Tổ hợp: {combo_code}")
    combo = await db.get(SubjectCombination, combo_code)
    if not combo: 
        logger.warning(f"[CRUD] Cập nhật Tổ hợp thất bại: Không tìm thấy {combo_code}")
        raise HTTPException(404, "Không tìm thấy")
    if combo_code != item.combo_code:
        stmt = select(SubjectCombination).where(SubjectCombination.combo_code == item.combo_code)
        if (await db.execute(stmt)).scalar_one_or_none():
            logger.warning(f"[CRUD] Cập nhật Tổ hợp thất bại: Mã mới {item.combo_code} đã tồn tại")
            raise HTTPException(400, "Mã tổ hợp mới đã tồn tại")
        new_combo = SubjectCombination(combo_code=item.combo_code, subjects=item.subjects)
        db.add(new_combo)
        await db.delete(combo)
    else:
        combo.subjects = item.subjects
    await db.commit()
    logger.info(f"[CRUD] Cập nhật Tổ hợp thành công: {combo_code}")
    return {"message": "Cập nhật thành công"}

@router.delete("/combinations/{combo_code}")
async def delete_combo(combo_code: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa Tổ hợp: {combo_code}")
    combo = await db.get(SubjectCombination, combo_code)
    if not combo: 
        logger.warning(f"[CRUD] Xóa Tổ hợp thất bại: Không tìm thấy {combo_code}")
        raise HTTPException(404, "Không tìm thấy")
    await db.delete(combo)
    await db.commit()
    logger.info(f"[CRUD] Xóa Tổ hợp thành công: {combo_code}")
    return {"message": "Xóa thành công"}

@router.post("/combinations/bulk-delete")
async def bulk_delete_combos(payload: BulkDeleteStr, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa hàng loạt Tổ hợp: {len(payload.ids)} mục")
    if not payload.ids:
        return {"message": "Không có mục nào được chọn để xóa"}
    stmt = delete(SubjectCombination).where(SubjectCombination.combo_code.in_(payload.ids))
    await db.execute(stmt)
    await db.commit()
    logger.info(f"[CRUD] Xóa hàng loạt Tổ hợp thành công")
    return {"message": f"Đã xóa thành công {len(payload.ids)} mục"}


# ---- PLANS ----
@router.post("/plans")
async def create_plan(item: PlanCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu thêm Đề án: Ngành {item.ma_nganh} ({item.nam})")
    
    # Ở đây ta không cần check existed (tùy vào logic), có thể 1 ngành/1 năm có nhiều phương thức
    new_plan = AdmissionPlan(
        ma_xet_tuyen=item.ma_xet_tuyen,
        ma_nganh=item.ma_nganh,
        nam=item.nam,
        ma_phuong_thuc=item.ma_phuong_thuc,
        khoi=item.khoi,
        diem_chuan=item.diem_chuan,
        hoc_ba_tbc_3_nam=item.hoc_ba_tbc_3_nam,
        diem_tot_nghiep=item.diem_tot_nghiep,
        tbc_3_nam_ngoai_ngu=item.tbc_3_nam_ngoai_ngu,
        hoc_luc_12=item.hoc_luc_12,
        nang_khieu=item.nang_khieu,
        mon_nhan_he_so=item.mon_nhan_he_so,
        tieng_anh=item.tieng_anh,
        ngoai_ngu=item.ngoai_ngu,
        he_so=item.he_so
    )
    db.add(new_plan)
    await db.commit()
    logger.info(f"[CRUD] Thêm Đề án thành công: Ngành {item.ma_nganh}")
    return {"message": "Thêm thành công"}

@router.put("/plans/{id}")
async def update_plan(id: int, item: PlanCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu cập nhật Đề án ID: {id}")
    plan = await db.get(AdmissionPlan, id)
    if not plan: 
        logger.warning(f"[CRUD] Cập nhật Đề án thất bại: Không tìm thấy ID {id}")
        raise HTTPException(404, "Không tìm thấy")
    
    plan.ma_xet_tuyen = item.ma_xet_tuyen
    plan.ma_nganh = item.ma_nganh
    plan.nam = item.nam
    plan.ma_phuong_thuc = item.ma_phuong_thuc
    plan.khoi = item.khoi
    plan.diem_chuan = item.diem_chuan
    plan.hoc_ba_tbc_3_nam = item.hoc_ba_tbc_3_nam
    plan.diem_tot_nghiep = item.diem_tot_nghiep
    plan.tbc_3_nam_ngoai_ngu = item.tbc_3_nam_ngoai_ngu
    plan.hoc_luc_12 = item.hoc_luc_12
    plan.nang_khieu = item.nang_khieu
    plan.mon_nhan_he_so = item.mon_nhan_he_so
    plan.tieng_anh = item.tieng_anh
    plan.ngoai_ngu = item.ngoai_ngu
    plan.he_so = item.he_so

    await db.commit()
    logger.info(f"[CRUD] Cập nhật Đề án thành công: ID {id}")
    return {"message": "Cập nhật thành công"}

@router.delete("/plans/{id}")
async def delete_plan(id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa Đề án ID: {id}")
    plan = await db.get(AdmissionPlan, id)
    if not plan: 
        logger.warning(f"[CRUD] Xóa Đề án thất bại: Không tìm thấy ID {id}")
        raise HTTPException(404, "Không tìm thấy")
    await db.delete(plan)
    await db.commit()
    logger.info(f"[CRUD] Xóa Đề án thành công: ID {id}")
    return {"message": "Xóa thành công"}

@router.post("/plans/bulk-delete")
async def bulk_delete_plans(payload: BulkDeleteInt, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa hàng loạt Đề án: {len(payload.ids)} mục")
    if not payload.ids:
        return {"message": "Không có mục nào được chọn để xóa"}
    stmt = delete(AdmissionPlan).where(AdmissionPlan.id.in_(payload.ids))
    await db.execute(stmt)
    await db.commit()
    logger.info(f"[CRUD] Xóa hàng loạt Đề án thành công")
    return {"message": f"Đã xóa thành công {len(payload.ids)} mục"}


# ---- QUOTAS ----
@router.post("/quotas")
async def create_quota(item: QuotaCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu thêm Chỉ tiêu: Mã XT {item.ma_xet_tuyen}")
    new_quota = AdmissionQuota(**item.model_dump())
    db.add(new_quota)
    await db.commit()
    logger.info(f"[CRUD] Thêm Chỉ tiêu thành công")
    return {"message": "Thêm thành công"}

@router.put("/quotas/{id}")
async def update_quota(id: int, item: QuotaCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu cập nhật Chỉ tiêu ID: {id}")
    quota = await db.get(AdmissionQuota, id)
    if not quota:
        raise HTTPException(404, "Không tìm thấy")
    
    for k, v in item.model_dump().items():
        setattr(quota, k, v)
    
    await db.commit()
    logger.info(f"[CRUD] Cập nhật Chỉ tiêu thành công")
    return {"message": "Cập nhật thành công"}

@router.delete("/quotas/{id}")
async def delete_quota(id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa Chỉ tiêu ID: {id}")
    quota = await db.get(AdmissionQuota, id)
    if not quota: 
        logger.warning(f"[CRUD] Xóa Chỉ tiêu thất bại: Không tìm thấy ID {id}")
        raise HTTPException(404, "Không tìm thấy")
    await db.delete(quota)
    await db.commit()
    logger.info(f"[CRUD] Xóa Chỉ tiêu thành công: ID {id}")
    return {"message": "Xóa thành công"}

@router.post("/quotas/bulk-delete")
async def bulk_delete_quotas(payload: BulkDeleteInt, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu xóa hàng loạt Chỉ tiêu: {len(payload.ids)} mục")
    if not payload.ids:
        return {"message": "Không có mục nào được chọn để xóa"}
    stmt = delete(AdmissionQuota).where(AdmissionQuota.id.in_(payload.ids))
    await db.execute(stmt)
    await db.commit()
    logger.info(f"[CRUD] Xóa hàng loạt Chỉ tiêu thành công")
    return {"message": f"Đã xóa thành công {len(payload.ids)} mục"}


