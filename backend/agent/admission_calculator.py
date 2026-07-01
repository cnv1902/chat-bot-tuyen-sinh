"""
agent/admission_calculator.py
=============================
Chứa các hàm tính toán điểm xét tuyển (Deterministic Code) và bóc tách
điều kiện phụ (Gating) để tránh hiện tượng ảo giác toán học của LLM.
"""

def calculate_final_score(subject_scores: dict, priority_score: float = 0.0, he_so: str | int | None = None, mon_nhan_he_so: str | None = None) -> float:
    """
    Tính điểm xét tuyển thực tế của thí sinh.
    
    Quy tắc:
    1. Tính tổng 3 môn.
    2. Nếu he_so == 2 (hoặc '2') và môn nhân hệ số có trong điểm:
       Quy đổi về thang 30 = (Tổng điểm + Điểm môn nhân hệ số) * 3/4
    3. Trượt điểm ưu tiên nếu Tổng điểm quy đổi >= 22.5:
       Điểm ưu tiên thực tế = [(30 - Tổng điểm quy đổi) / 7.5] * Mức điểm ưu tiên
    4. Tổng điểm cuối = Tổng điểm quy đổi + Điểm ưu tiên thực tế (Tối đa 30)
    """
    if not subject_scores:
        return 0.0
        
    # Tính tổng 3 môn
    base_score = sum(float(v) for v in subject_scores.values())
    
    # Xét hệ số môn nhân đôi
    if str(he_so).strip() == "2" and mon_nhan_he_so:
        # Tìm key trong subject_scores khớp (case-insensitive) với mon_nhan_he_so
        matched_score = 0.0
        target = mon_nhan_he_so.lower().strip()
        for k, v in subject_scores.items():
            if k.lower().strip() == target:
                matched_score = float(v)
                break
        
        # Nếu có môn nhân hệ số, áp dụng công thức quy đổi thang 30
        if matched_score > 0:
            base_score = (base_score + matched_score) * 0.75
            
    # Tính điểm ưu tiên trượt
    priority_score = float(priority_score)
    actual_priority = priority_score
    if base_score >= 22.5:
        actual_priority = ((30.0 - base_score) / 7.5) * priority_score
        
    final_score = base_score + actual_priority
    return round(min(30.0, final_score), 2)


def generate_gating_text(record: dict) -> str:
    """
    Bóc tách các trường điều kiện (Gating) từ bản ghi thành một chuỗi văn bản tự nhiên.
    Các trường bị Null sẽ được bỏ qua.
    """
    conditions = []
    
    diem_hoc_ba = record.get("diem_hoc_ba")
    if diem_hoc_ba:
        conditions.append(f"Điểm học bạ TBC 3 năm tối thiểu: {diem_hoc_ba}")
        
    diem_tot_nghiep = record.get("diem_tot_nghiep")
    if diem_tot_nghiep:
        conditions.append(f"Điểm thi tốt nghiệp THPT tối thiểu: {diem_tot_nghiep}")
        
    tbc_3_nam_ngoai_ngu = record.get("tbc_3_nam_ngoai_ngu")
    if tbc_3_nam_ngoai_ngu:
        conditions.append(f"TBC 3 năm ngoại ngữ tối thiểu: {tbc_3_nam_ngoai_ngu}")
        
    hoc_luc_12 = record.get("hoc_luc_12")
    if hoc_luc_12:
        conditions.append(f"Học lực lớp 12: {hoc_luc_12}")
        
    nang_khieu = record.get("nang_khieu")
    if nang_khieu:
        conditions.append(f"Điểm thi Năng khiếu tối thiểu: {nang_khieu}")
        
    tieng_anh = record.get("tieng_anh")
    if tieng_anh:
        conditions.append(f"Yêu cầu Tiếng Anh: {tieng_anh}")
        
    ngoai_ngu = record.get("ngoai_ngu")
    if ngoai_ngu:
        conditions.append(f"Yêu cầu Ngoại ngữ khác: {ngoai_ngu}")
        
    if not conditions:
        return "Không có điều kiện phụ."
        
    return "; ".join(conditions)
