"""
agent/tools.py
==============
Hai công cụ lõi phục vụ Agentic RAG.
- Tool 1: Truy vấn thông tin cứng (dữ liệu tuyển sinh trên RAM).
- Tool 2: Truy vấn thông tin mềm (Qdrant semantic search với 3-step fallback).
"""

import logging
from typing import Optional, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from rapidfuzz import process, fuzz

from core.cache_service import get_admission_cache, normalize_and_map_alias
from core.embedder import embed
from core.vectordb import search as qdrant_search
from core.query_expansion import expand_query, normalize_entity_name
from agent.admission_calculator import calculate_final_score, generate_gating_text

logger = logging.getLogger(__name__)

import json

def group_admission_records(records: list) -> dict:
    grouped = {}
    
    condition_keys = [
        "hoc_ba_tb_3_nam_min", "diem_tot_nghiep_min", "ngoai_ngu_tb_3_nam_min", 
        "hoc_luc_12_min", "nang_khieu_min", "tieng_anh_min", "ngoai_ngu_min", 
        "mon_nhan_he_so", "he_so"
    ]
    
    for record in records:
        nganh = record.get("ten_nganh")
        if not nganh:
            continue
            
        chuong_trinh = record.get("ten_chuong_trinh") or record.get("ma_xet_tuyen") or "Chương trình tiêu chuẩn"
        
        if nganh not in grouped:
            grouped[nganh] = {}
            
        if chuong_trinh not in grouped[nganh]:
            grouped[nganh][chuong_trinh] = []
            
        dieu_kien_phu = {}
        for k in condition_keys:
            val = record.get(k)
            if val is not None and val != "":
                dieu_kien_phu[k] = val
                
        phuong_thuc = {}
        for k in ["phuong_thuc", "ma_phuong_thuc", "khoi", "chi_tieu", "diem_chuan"]:
            val = record.get(k)
            if val is not None and val != "":
                phuong_thuc[k] = val
                
        if dieu_kien_phu:
            phuong_thuc["dieu_kien_phu"] = dieu_kien_phu
            
        grouped[nganh][chuong_trinh].append(phuong_thuc)
        
    return grouped

# ===========================================================================
# Tool 1: query_admission_data
# ===========================================================================

class QueryAdmissionDataInput(BaseModel):
    major_or_program_name: Optional[str] = Field(None, description="Tên ngành, tên chương trình đào tạo, hoặc mã ngành thí sinh muốn hỏi (VD: 'Công nghệ thông tin', 'Sư phạm Toán chất lượng cao', '7480201'). Hãy trích xuất nguyên văn cụm từ thí sinh dùng.")
    year: Optional[int] = Field(None, description="Năm tuyển sinh (vd: 2026)")
    subject_group: Optional[str] = Field(None, description="Tổ hợp môn/Khối thi (vd: A00, D01)")
    admission_method: Optional[str] = Field(None, description="Mã hoặc tên phương thức xét tuyển")
    user_exam_score: Optional[float] = Field(None, description="Điểm thi tốt nghiệp hoặc ĐGNL của thí sinh")
    user_transcript_score: Optional[float] = Field(None, description="Điểm xét học bạ của thí sinh")

@tool("query_admission_data", args_schema=QueryAdmissionDataInput)
def query_admission_data(
    major_or_program_name: Optional[str] = None,
    year: Optional[int] = None,
    subject_group: Optional[str] = None,
    admission_method: Optional[str] = None,
    user_exam_score: Optional[float] = None,
    user_transcript_score: Optional[float] = None,
) -> str:
    """
    Truy vấn thông tin cấu trúc như mã ngành, điểm chuẩn, tổ hợp xét tuyển, phương thức tuyển sinh.
    Ưu tiên gọi tool này khi người dùng hỏi các số liệu cụ thể.
    """
    if major_or_program_name:
        old_val = major_or_program_name
        major_or_program_name = normalize_entity_name(major_or_program_name)
        if major_or_program_name != old_val:
            logger.info(f"[Normalize] Tên ngành gốc: {old_val} -> Chuẩn hóa: {major_or_program_name}")

    logger.info(f"[Tool] query_admission_data called with: major_or_program={major_or_program_name}, year={year}, subject_group={subject_group}, method={admission_method}, exam_score={user_exam_score}, transcript_score={user_transcript_score}")
    
    try:
        cache_data = get_admission_cache()
        if not cache_data:
            return "Xin lỗi, hiện tại dữ liệu tuyển sinh chưa sẵn sàng. Vui lòng liên hệ Hotline tuyển sinh."

        # Bước 1 (Lọc cứng)
        # Lọc theo year
        if year is not None:
            cache_data = [r for r in cache_data if r.get("nam") == year]
            
        # Lọc theo subject_group
        if subject_group:
            sg_lower = subject_group.lower().strip()
            cache_data = [r for r in cache_data if r.get("khoi") and sg_lower in r["khoi"].lower()]
            
        # Lọc theo admission_method
        if admission_method:
            am_lower = admission_method.lower().strip()
            cache_data = [r for r in cache_data if r.get("ma_phuong_thuc") and am_lower in r["ma_phuong_thuc"].lower()]

        # Lọc theo major_or_program_name bằng Combined String Fuzzy Matching
        if major_or_program_name:
            normalized_target = normalize_and_map_alias(major_or_program_name)
            matched_records = []
            
            for r in cache_data:
                target_str = f"{r.get('ma_nganh', '')} {r.get('ten_nganh', '')} {r.get('ten_chuong_trinh', '')}".lower()
                score = fuzz.WRatio(normalized_target, target_str)
                if score > 70:
                    matched_records.append(r)
            
            if not matched_records:
                logger.warning(f"[Tool] Không tìm thấy ngành phù hợp với: '{major_or_program_name}'")
                return f"Hệ thống không tìm thấy dữ liệu cho '{major_or_program_name}'. Hãy hướng dẫn thí sinh xác nhận lại."
                
            cache_data = matched_records
            logger.info(f"[Tool] Fuzzy match cho '{major_or_program_name}' -> tìm thấy {len(matched_records)} records")
            
        # Bước 2 (Lọc Điều kiện tối thiểu - Smart Thresholds)
        def safe_float(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
                
        if user_exam_score is not None:
            cache_data = [
                r for r in cache_data 
                if not r.get("diem_tot_nghiep") or (safe_float(r.get("diem_tot_nghiep")) is not None and safe_float(r.get("diem_tot_nghiep")) <= user_exam_score)
            ]
            
        if user_transcript_score is not None:
            cache_data = [
                r for r in cache_data 
                if not r.get("diem_hoc_ba") or (safe_float(r.get("diem_hoc_ba")) is not None and safe_float(r.get("diem_hoc_ba")) <= user_transcript_score)
            ]
            
        # Bước 3 (Bảo vệ Token & JSON Grouping)
        if not cache_data:
            return "Không tìm thấy ngành học nào thỏa mãn điểm số hoặc điều kiện của bạn."
            
        logger.info(f"[Tool] Tìm thấy {len(cache_data)} kết quả phù hợp.")
        
        limit = 40 # Nới lỏng số dòng một chút vì JSON cấu trúc tiết kiệm token hơn
        grouped_data = group_admission_records(cache_data[:limit])
        
        output_str = f"""Dưới đây là dữ liệu tuyển sinh dạng JSON đã được gom nhóm.
[HƯỚNG DẪN ĐỌC DỮ LIỆU CỐT LÕI]:

1. Cấu trúc: Mỗi 'ten_chuong_trinh_dao_tao' là một nhánh chuyên ngành riêng biệt. Một ngành có thể có nhiều chuyên ngành và nhiều phương thức xét tuyển. Hãy liệt kê đầy đủ để không gây hiểu nhầm.
2. Ràng buộc: Các điều kiện trong 'dieu_kien_phu' CHỈ áp dụng riêng cho phương thức xét tuyển chứa nó, TUYỆT ĐỐI KHÔNG áp dụng chung cho cả ngành.
3. Giải nghĩa các trường dữ liệu điều kiện và tính điểm (Nếu có):
* 'hoc_ba_tb_3_nam_min': Tổng điểm trung bình chung học bạ 3 năm THPT tối thiểu.
* 'diem_tot_nghiep_min': Tổng điểm thi tốt nghiệp THPT tối thiểu.
* 'ngoai_ngu_tb_3_nam_min': Điểm trung bình môn Ngoại ngữ 3 năm THPT tối thiểu.
* 'hoc_luc_12_min': Xếp loại học lực năm lớp 12 tối thiểu (VD: Khá, Giỏi).
* 'nang_khieu_min': Điểm thi môn Năng khiếu tối thiểu.
* 'tieng_anh_min' / 'ngoai_ngu_min': Điểm thi môn Tiếng Anh / Ngoại ngữ tối thiểu.
* 'mon_nhan_he_so': Tên môn học trong tổ hợp xét tuyển được áp dụng nhân hệ số.
* 'he_so': Mức hệ số (thường là 2) nhân vào điểm của môn quy định ở trường 'mon_nhan_he_so' khi tính tổng điểm xét tuyển.

[DỮ LIỆU JSON]:
{json.dumps(grouped_data, ensure_ascii=False, indent=2)}
"""
        if len(cache_data) > limit:
            output_str += f"\n... và {len(cache_data) - limit} bản ghi khác đã bị ẩn đi. Vui lòng hướng dẫn thí sinh cung cấp thêm thông tin để thu hẹp tìm kiếm."

        return output_str
        
    except Exception as e:
        logger.error(f"[Tool] Lỗi trong quá trình truy vấn query_admission_data: {str(e)}", exc_info=True)
        return "Rất tiếc, đã có lỗi hệ thống khi truy vấn dữ liệu tuyển sinh."


# ===========================================================================
# Tool MỚI: check_admission_eligibility
# ===========================================================================

class CheckAdmissionEligibilityInput(BaseModel):
    subject_scores: dict[str, float] = Field(..., description="Từ điển lưu điểm thi các môn của thí sinh. Ví dụ: {'Toán': 8, 'Lý': 7, 'Tiếng Anh': 9}")
    priority_score: float = Field(0.0, description="Điểm ưu tiên khu vực/đối tượng (Mặc định 0)")
    target_major: str = Field(..., description="Tên ngành hoặc mã ngành thí sinh muốn xét tuyển")

@tool("check_admission_eligibility", args_schema=CheckAdmissionEligibilityInput)
def check_admission_eligibility(
    subject_scores: dict[str, float],
    target_major: str,
    priority_score: float = 0.0,
) -> str:
    """
    Thẩm định hồ sơ thí sinh: Tính điểm xét tuyển thực tế (áp dụng trượt điểm ưu tiên, nhân hệ số) và so sánh với điểm chuẩn để kết luận Đỗ/Trượt.
    Chỉ sử dụng tool này khi thí sinh hỏi "Em có đỗ không?", "Điểm em thế này đỗ ngành X không?".
    """
    if target_major:
        old_val = target_major
        target_major = normalize_entity_name(target_major)
        if target_major != old_val:
            logger.info(f"[Normalize] Tên ngành gốc: {old_val} -> Chuẩn hóa: {target_major}")

    logger.info(f"[Tool] check_admission_eligibility called: target={target_major}, scores={subject_scores}, priority={priority_score}")
    
    try:
        cache_data = get_admission_cache()
        if not cache_data:
            return "Hệ thống chưa tải dữ liệu tuyển sinh."
            
        normalized_target = normalize_and_map_alias(target_major)
        matched_records = []
        
        # Tìm các ngành khớp
        for r in cache_data:
            target_str = f"{r.get('ma_nganh', '')} {r.get('ten_nganh', '')} {r.get('ten_chuong_trinh', '')}".lower()
            score = fuzz.WRatio(normalized_target, target_str)
            if score > 70:
                matched_records.append(r)
                
        if not matched_records:
            return f"Hệ thống không tìm thấy ngành/chương trình nào tên là '{target_major}'."
            
        lines = []
        # Giới hạn 10 bản ghi để tránh token quá dài
        for r in matched_records[:10]:
            # Chỉ lấy các bản ghi có diem_chuan
            diem_chuan_str = r.get("diem_chuan")
            if not diem_chuan_str:
                continue
                
            try:
                diem_chuan = float(diem_chuan_str)
            except ValueError:
                continue
                
            final_score = calculate_final_score(
                subject_scores=subject_scores,
                priority_score=priority_score,
                he_so=r.get("he_so"),
                mon_nhan_he_so=r.get("mon_nhan_he_so")
            )
            
            is_eligible = final_score >= diem_chuan
            ket_luan = "ĐỦ ĐIỀU KIỆN" if is_eligible else "KHÔNG ĐỦ ĐIỀU KIỆN"
            gating_text = generate_gating_text(r)
            
            lines.append(
                f"Ngành: {r.get('ten_nganh')} | Mã XT: {r.get('ma_nganh')} | Khối: {r.get('khoi')} | Điểm chuẩn: {diem_chuan}\n"
                f"Điểm của thí sinh (Đã quy đổi hệ số & cộng ưu tiên): {final_score}\n"
                f"Kết luận: {ket_luan} trúng tuyển.\n"
                f"Điều kiện phụ (Gating): {gating_text}\n"
                f"-" * 20
            )
            
        if not lines:
            return f"Ngành '{target_major}' chưa có dữ liệu điểm chuẩn rõ ràng để thẩm định."
            
        return "Kết quả thẩm định hồ sơ:\n\n" + "\n".join(lines)
        
    except Exception as e:
        logger.error(f"[Tool] Lỗi khi check_admission_eligibility: {str(e)}", exc_info=True)
        return "Có lỗi xảy ra trong quá trình tính toán điểm thi. Vui lòng hướng dẫn thí sinh tự tính toán."


# ===========================================================================
# Tool 2: search_unstructured_knowledge
# ===========================================================================

class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., description="Câu hỏi tìm kiếm semantic (vd: Điều kiện xét học bạ, sinh viên có được ở ký túc xá không)")
    year: Optional[int] = Field(None, description="Năm áp dụng tài liệu. CHỈ ĐIỀN NẾU CHẮC CHẮN.")
    doc_type: Optional[str] = Field(None, description="Loại tài liệu (de_an, quy_che, hoc_phi). CHỈ ĐIỀN NẾU CHẮC CHẮN.")

@tool("search_unstructured_knowledge", args_schema=SearchKnowledgeInput)
def search_unstructured_knowledge(
    query: str,
    year: Optional[int] = None,
    doc_type: Optional[str] = None,
) -> str:
    """
    Tìm kiếm thông tin trong các văn bản quy chế, đề án, hướng dẫn, học phí, giới thiệu trường.
    Ưu tiên gọi tool này khi người dùng hỏi các câu hỏi chung, thủ tục, quy định, mô tả, đời sống, cơ sở vật chất.
    """
    logger.info(f"[Tool] search_unstructured_knowledge called: query='{query}', year={year}, doc_type={doc_type}")
    
    # Bước 0: Mở rộng từ khóa (Sparse Expansion) và Tạo vector
    try:
        expanded_query = expand_query(query)
        if expanded_query != query:
            logger.info(f"[Tool] Query expanded: '{query}' -> '{expanded_query}'")
        query_vector = embed(expanded_query)
    except Exception as e:
        logger.error(f"[Tool] Embed failed: {str(e)}")
        return "Xin lỗi, hiện tại không thể tìm kiếm tài liệu (Lỗi vectorization)."

    # Hàm tiện ích gọi qdrant (Hybrid RRF)
    def do_search(filters: dict) -> list[dict]:
        return qdrant_search(query_vector=query_vector, filters=filters, top_k=3, score_threshold=0.01)

    # Phễu nới lỏng 3 bước (Cascading Fallback)
    
    # Bước 1: Strict filter
    strict_filters = {}
    if year: strict_filters["year"] = year
    if doc_type: strict_filters["doc_type"] = doc_type
    
    results = do_search(strict_filters)
    
    if results:
        logger.info("[Tool] Search thành công ở Bước 1 (Strict filter).")
    else:
        logger.info("[Tool] Qdrant Strict search failed. Falling back to Relaxed search 1 (bỏ doc_type)...")
        # Bước 2: Relaxed 1 (chỉ year)
        relaxed_filters_1 = {}
        if year: relaxed_filters_1["year"] = year
        
        if relaxed_filters_1 != strict_filters:
            results = do_search(relaxed_filters_1)
            
        if results:
            logger.info("[Tool] Search thành công ở Bước 2 (Relaxed 1).")
        else:
            logger.info("[Tool] Qdrant Relaxed search 1 failed. Falling back to Pure Semantic search...")
            # Bước 3: Semantic thuần túy (không filter)
            results = do_search({})
            if results:
                logger.info("[Tool] Search thành công ở Bước 3 (Pure Semantic).")

    if not results:
        return "Tôi không tìm thấy thông tin văn bản nào liên quan đến câu hỏi của bạn."

    # Format output
    lines = []
    for r in results:
        content = r.get("content", "").strip()
        metadata = r.get("metadata", {})
        source_file = metadata.get("source_file", "Cơ sở dữ liệu")
        
        lines.append(f"--- Nguồn: {source_file} ---\n{content}\n")
        
    return "Thông tin tìm thấy:\n\n" + "\n".join(lines)
