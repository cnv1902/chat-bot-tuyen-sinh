import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from rapidfuzz import fuzz
import unicodedata
import re

from core.session import _get_client
from db.models import Account, StaffProfile, RoleEnum, AdmissionCode, Major

logger = logging.getLogger(__name__)

def normalize_string(text: str) -> str:
    """Chuẩn hóa chuỗi: bỏ dấu tiếng Việt, viết thường, xoá khoảng trắng thừa."""
    if not text:
        return ""
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return " ".join(text.split())

async def sync_staff_to_redis(db: AsyncSession):
    """
    Đồng bộ danh sách Cán bộ lên Redis Hash.
    Join StaffProfile với AdmissionCode và Major để tạo chuỗi searchable_programs.
    Format Hash: staff:{staff_id}
      - username
      - full_name
      - role
      - avatar_url
      - is_online (1/0)
      - searchable_programs (Chuỗi tổng hợp)
    """
    try:
        redis = _get_client()
        
        # Lấy tất cả Staff
        stmt = select(Account, StaffProfile).join(
            StaffProfile, Account.account_id == StaffProfile.account_id
        ).where(
            Account.role.in_([RoleEnum.STAFF_TRUONG, RoleEnum.STAFF_NGANH]),
            Account.is_active == True
        )
        result = await db.execute(stmt)
        staff_list = result.all()

        # Cache trước AdmissionCode JOIN Major để tránh N+1 queries
        code_stmt = select(AdmissionCode, Major).join(
            Major, AdmissionCode.major_code == Major.major_code
        )
        code_result = await db.execute(code_stmt)
        # Tạo từ điển map admission_code -> thông tin ngành
        code_dict = {}
        for adm, maj in code_result.all():
            code_dict[adm.admission_code] = {
                "admission_code": adm.admission_code,
                "program_name": adm.program_name,
                "major_code": maj.major_code,
                "major_name": maj.major_name
            }

        synced_count = 0
        for account, profile in staff_list:
            searchable_programs = ""
            managed_codes = []
            
            if account.role == RoleEnum.STAFF_NGANH and profile.managed_programs:
                # Tách mảng admission_code từ chuỗi (ví dụ "7480201CN, 7480201CLC")
                raw_codes = [c.strip() for c in profile.managed_programs.split(",")]
                
                for code in raw_codes:
                    if not code: continue
                    managed_codes.append(code)
                    info = code_dict.get(code)
                    if info:
                        # Ghép tất cả thành chuỗi ngữ nghĩa lớn
                        searchable_programs += f"{info['admission_code']} {info['program_name']} {info['major_code']} {info['major_name']} | "
                    else:
                        searchable_programs += f"{code} | "
            
            # Chuẩn hóa chuỗi tìm kiếm để fuzzy match dễ dàng hơn
            normalized_searchable = normalize_string(searchable_programs)

            # Map kiểu dữ liệu cẩn thận
            hash_key = f"staff:{profile.staff_id}"
            hash_data = {
                "staff_id": str(profile.staff_id),
                "account_id": str(account.account_id),
                "username": str(account.username),
                "full_name": str(profile.full_name or ""),
                "role": str(account.role.value),
                "avatar_url": str(profile.avatar_url or ""),
                "is_online": "1" if profile.is_online else "0",
                "searchable_programs": normalized_searchable,
                "managed_codes_raw": ",".join(managed_codes)
            }
            
            redis.hset(hash_key, mapping=hash_data)
            synced_count += 1
            
        logger.info(f"[StaffRouting] Đã đồng bộ {synced_count} Cán bộ lên Redis thành công với Rich Text Indexing.")
    except Exception as e:
        logger.error(f"[StaffRouting] Lỗi đồng bộ cán bộ: {e}", exc_info=True)


def find_best_staff(target_major_or_program: Optional[str] = None) -> Optional[dict]:
    """
    Quét Redis để tìm cán bộ online phù hợp nhất dựa vào fuzzy match.
    """
    try:
        redis = _get_client()
        keys = redis.keys("staff:*")
        
        best_staff = None
        best_score = 0
        fallback_staff = None
        
        normalized_target = normalize_string(target_major_or_program) if target_major_or_program else ""

        for key in keys:
            staff_data = redis.hgetall(key)
            if not staff_data: continue
            
            # Parse is_online an toàn từ bytes/str
            raw_is_online = staff_data.get("is_online") or staff_data.get(b"is_online")
            is_online = str(raw_is_online).lower() in ["1", "true", "b'1'", "b'true'"]
            
            if not is_online:
                continue

            # Decode các trường cần thiết
            role_raw = staff_data.get("role") or staff_data.get(b"role", b"")
            role = role_raw.decode('utf-8', errors='ignore') if isinstance(role_raw, bytes) else str(role_raw)
            
            staff_id_raw = staff_data.get("staff_id") or staff_data.get(b"staff_id", b"")
            staff_id = staff_id_raw.decode('utf-8') if isinstance(staff_id_raw, bytes) else str(staff_id_raw)
            
            username_raw = staff_data.get("username") or staff_data.get(b"username", b"")
            username = username_raw.decode('utf-8') if isinstance(username_raw, bytes) else str(username_raw)
            
            full_name_raw = staff_data.get("full_name") or staff_data.get(b"full_name", b"")
            full_name = full_name_raw.decode('utf-8') if isinstance(full_name_raw, bytes) else str(full_name_raw)
            
            avatar_url_raw = staff_data.get("avatar_url") or staff_data.get(b"avatar_url", b"")
            avatar_url = avatar_url_raw.decode('utf-8') if isinstance(avatar_url_raw, bytes) else str(avatar_url_raw)

            staff_dict = {
                "staff_id": staff_id,
                "username": username,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "role": role
            }

            if role == "RoleEnum.STAFF_TRUONG" or role == "STAFF_TRUONG":
                if fallback_staff is None:
                    fallback_staff = staff_dict
            
            if (role == "RoleEnum.STAFF_NGANH" or role == "STAFF_NGANH") and normalized_target:
                searchable_raw = staff_data.get("searchable_programs") or staff_data.get(b"searchable_programs", b"")
                searchable_programs = searchable_raw.decode('utf-8', errors='ignore') if isinstance(searchable_raw, bytes) else str(searchable_raw)
                
                # So khớp mờ
                score = fuzz.WRatio(normalized_target, searchable_programs)
                if score > best_score and score > 70:
                    best_score = score
                    best_staff = staff_dict

        # Nếu tìm thấy người khớp ngành thì trả về, nếu không fallback về STAFF_TRUONG
        return best_staff if best_staff else fallback_staff

    except Exception as e:
        logger.error(f"[StaffRouting] Lỗi tìm cán bộ: {e}", exc_info=True)
        return None
