from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import List, Optional

from db.connection import get_db
from db.models import SubjectCombination, AdmissionMethod, AdmissionPlan
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
    year: int
    major_code: str
    methods: List[str]
    combinations: List[str]
    target_quota: Optional[int] = None

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
    logger.info(f"[CRUD] Yêu cầu thêm Đề án: Ngành {item.major_code} ({item.year})")
    stmt = select(AdmissionPlan).where(AdmissionPlan.year == item.year, AdmissionPlan.major_code == item.major_code)
    if (await db.execute(stmt)).scalar_one_or_none():
        logger.warning(f"[CRUD] Thêm Đề án thất bại: Ngành {item.major_code} đã có đề án năm {item.year}")
        raise HTTPException(400, "Đề án của ngành trong năm này đã tồn tại")
        
    new_plan = AdmissionPlan(
        year=item.year, major_code=item.major_code, 
        methods=item.methods, combinations=item.combinations, target_quota=item.target_quota
    )
    db.add(new_plan)
    await db.commit()
    logger.info(f"[CRUD] Thêm Đề án thành công: Ngành {item.major_code}")
    return {"message": "Thêm thành công"}

@router.put("/plans/{id}")
async def update_plan(id: int, item: PlanCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"[CRUD] Yêu cầu cập nhật Đề án ID: {id}")
    plan = await db.get(AdmissionPlan, id)
    if not plan: 
        logger.warning(f"[CRUD] Cập nhật Đề án thất bại: Không tìm thấy ID {id}")
        raise HTTPException(404, "Không tìm thấy")
    
    plan.year = item.year
    plan.major_code = item.major_code
    plan.methods = item.methods
    plan.combinations = item.combinations
    plan.target_quota = item.target_quota
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

