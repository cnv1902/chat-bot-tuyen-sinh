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

logger = logging.getLogger(__name__)

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
            
        # Bước 3 (Bảo vệ Token)
        if not cache_data:
            return "Không tìm thấy ngành học nào thỏa mãn điểm số hoặc điều kiện của bạn."
            
        logger.info(f"[Tool] Tìm thấy {len(cache_data)} kết quả phù hợp.")
            
        lines = []
        limit = 15
        for r in cache_data[:limit]:
            line = f"- Ngành: {r.get('ten_nganh')} - Chương trình: {r.get('ten_chuong_trinh')} (Mã: {r.get('ma_nganh')})"
            if r.get('institute_name'): line += f" thuộc {r.get('institute_name')}"
            if r.get("nam"): line += f" | Năm: {r.get('nam')}"
            if r.get("diem_chuan"): line += f" | Điểm chuẩn: {r.get('diem_chuan')}"
            if r.get("khoi"): line += f" | Tổ hợp: {r.get('khoi')}"
            if r.get("chi_tieu"): line += f" | Chỉ tiêu: {r.get('chi_tieu')}"
            if r.get("diem_tot_nghiep"): line += f" | ĐK điểm tốt nghiệp: {r.get('diem_tot_nghiep')}"
            if r.get("diem_hoc_ba"): line += f" | ĐK điểm học bạ: {r.get('diem_hoc_ba')}"
            lines.append(line)
            
        if len(cache_data) > limit:
            lines.append(f"\n... và {len(cache_data) - limit} ngành khác. Vui lòng hướng dẫn thí sinh cung cấp thêm tổ hợp môn hoặc sở thích để thu hẹp kết quả.")

        lines.append("--- Nguồn: Cơ sở dữ liệu ---")
        return "Đây là kết quả tra cứu:\n" + "\n".join(lines)
        
    except Exception as e:
        logger.error(f"[Tool] Lỗi trong quá trình truy vấn query_admission_data: {str(e)}", exc_info=True)
        return "Rất tiếc, đã có lỗi hệ thống khi truy vấn dữ liệu tuyển sinh."


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
    
    # Bước 0: Tạo vector
    try:
        query_vector = embed(query)
    except Exception as e:
        logger.error(f"[Tool] Embed failed: {str(e)}")
        return "Xin lỗi, hiện tại không thể tìm kiếm tài liệu (Lỗi vectorization)."

    # Hàm tiện ích gọi qdrant
    def do_search(filters: dict) -> list[dict]:
        return qdrant_search(query_vector=query_vector, filters=filters, top_k=3, score_threshold=0.3)

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
