import re

# Từ điển các cụm từ đồng nghĩa / viết tắt (Synonym Dictionary)
# Key: Pattern (regex hoặc từ khóa)
# Value: Danh sách các từ đồng nghĩa cần bổ sung vào query
SYNONYM_DICT = {
    # ==========================================
    # 1. KHỐI NGÀNH CÔNG NGHỆ & KỸ THUẬT (Tech & Engineering)
    # ==========================================
    r"\b(cntt|it)\b": ["Công nghệ thông tin", "7480201"],
    r"\b(ktpm)\b": ["Kỹ thuật phần mềm", "7480103"],
    r"\b(khmt)\b": ["Khoa học máy tính", "7480101"],
    r"\b(httt)\b": ["Hệ thống thông tin", "7480104"],
    r"\b(attt)\b": ["An toàn thông tin", "7480202"],
    r"\b(ttnt|ai)\b": ["Trí tuệ nhân tạo", "7480201CN"], 
    r"\b(ptdl|da|data)\b": ["Phân tích dữ liệu", "Khoa học dữ liệu"], # Sửa ptdldl thành ptdl cho tự nhiên
    r"\b(cđt|cdt|co dien tu)\b": ["Cơ điện tử", "Công nghệ kỹ thuật cơ điện tử", "7510203"],
    r"\b(tđh|tdh|tu dong hoa)\b": ["Tự động hóa", "Điều khiển và tự động hóa", "7510303"],
    r"\b(oto|ô\s*tô)\b": ["Công nghệ kỹ thuật ô tô", "Kỹ thuật ô tô", "7510205"],
    r"\b(cntp|cn thực phẩm)\b": ["Công nghệ thực phẩm", "7540101"],
    r"\b(xd|xdung|xay dung)\b": ["Kỹ thuật xây dựng", "7580201"], # BỔ SUNG
    r"\b(dtvt|đtvt)\b": ["Kỹ thuật điện tử viễn thông", "Điện tử viễn thông", "7520207"], # BỔ SUNG
    r"\b(ktđ|ktđđ|dien dan dung)\b": ["Kỹ thuật điện", "Công nghệ kỹ thuật điện", "7520201"], # BỔ SUNG

    # ==========================================
    # 2. KHỐI NGÀNH KINH TẾ & QUẢN LÝ (Business & Management)
    # ==========================================
    r"\b(qtkd)\b": ["Quản trị kinh doanh", "7340101"],
    r"\b(tmdt|tmđt)\b": ["Thương mại điện tử", "7340122"],
    r"\b(mkt|marketing)\b": ["Marketing", "7340115"],
    r"\b(tcnh)\b": ["Tài chính Ngân hàng", "7340201"],
    r"\b(qtnl|qtns|nhan su)\b": ["Quản trị nhân lực", "Quản trị nhân sự", "7340404"],
    r"\b(ktoan|ke toan)\b": ["Kế toán", "7340301"], # Tách riêng kế toán để tránh trùng với Kinh tế
    r"\b(auditing|kiem toan)\b": ["Kiểm toán", "7340302"], # BỔ SUNG
    r"\b(kt|kinh te)\b": ["Kinh tế", "7310101", "Kinh tế phát triển", "Kinh tế đầu tư"], 
    r"\b(logistics|lgst)\b": ["Quản lý chuỗi cung ứng", "Logistics và quản lý chuỗi cung ứng", "7340116"], # Sửa mã ngành chuẩn ngành này là 7340116
    r"\b(lhqt|bng|ngoai giao)\b": ["Luật học", "7380101", "Luật kinh tế", "7380107"], # BỔ SUNG KHỐI LUẬT
    r"\b(qtks|qthl|nhks)\b": ["Quản trị khách sạn", "7810201", "Quản trị dịch vụ du lịch và lữ hành", "7810103"], # BỔ SUNG

    # ==========================================
    # 3. KHỐI NGÀNH NGOẠI NGỮ & SƯ PHẠM (Languages & Education)
    # ==========================================
    r"\b(nna|nn\s*anh)\b": ["Ngôn ngữ Anh", "7220201"],
    r"\b(nntq|nn\s*trung|tiếng\s*trung)\b": ["Ngôn ngữ Trung Quốc", "7220204"],
    r"\b(nnh|nn\s*hàn|tiếng\s*hàn)\b": ["Ngôn ngữ Hàn Quốc", "7220210"],
    r"\b(nnn|nn\s*nhật|tiếng\s*nhật)\b": ["Ngôn ngữ Nhật", "7220209"],
    r"\b(gdmn|mầm\s*non)\b": ["Giáo dục mầm non", "7140201"],
    r"\b(gdth|tiểu\s*học)\b": ["Giáo dục tiểu học", "7140202"],
    r"\b(sp\s*toán)\b": ["Sư phạm Toán học", "7140209"],
    r"\b(sp\s*văn)\b": ["Sư phạm Ngữ văn", "7140217"],
    r"\b(sp\s*anh)\b": ["Sư phạm Tiếng Anh", "7140231"],
    r"\b(tlh|tam ly hoc)\b": ["Tâm lý học", "7310401", "Tâm lý học giáo dục"], # BỔ SUNG

    # ==========================================
    # 4. HÀNH CHÍNH & ĐỜI SỐNG SINH VIÊN (Admin & Student Life)
    # ==========================================
    r"\b(ktx)\b": ["Ký túc xá", "Chỗ ở", "Nội trú"],
    r"\b(csvc)\b": ["Cơ sở vật chất", "Trang thiết bị", "Trường học"],
    r"\b(hp)\b": ["Học phí", "Tiền học", "Nộp tiền"],
    r"\b(hb)\b": ["Học bổng", "Khuyến khích học tập"],
    r"\b(đrl|drl)\b": ["Điểm rèn luyện", "Đánh giá rèn luyện"],
    r"\b(cđr|cdr)\b": ["Chuẩn đầu ra", "Điều kiện tốt nghiệp", "Anh văn đầu ra"],
    r"\b(nckh)\b": ["Nghiên cứu khoa học", "Đề tài sinh viên"],
    r"\b(clc)\b": ["Chất lượng cao", "Chương trình tiên tiến", "Chương trình tài năng"],
    r"\b(thptqg|thpt)\b": ["Trung học phổ thông", "Tốt nghiệp", "Thi quốc gia"],
    r"\b(đgnl|dgnl)\b": ["Đánh giá năng lực"],
    r"\b(tkb)\b": ["Thời khóa biểu", "Lịch học", "Lịch báo giảng"], 
    r"\b(ptxt)\b": ["Phương thức xét tuyển", "Hình thức xét tuyển", "Cách thức tuyển sinh"],
    r"\b(đkmh|dkmh|dktc|đktc)\b": ["Đăng ký môn học", "Đăng ký tín chỉ", "ĐKHP"], # Sửa dkff -> dktc
    r"\b(bhyt|bhtn)\b": ["Bảo hiểm y tế", "Bảo hiểm tai nạn", "Bảo hiểm sinh viên"], # Sửa lặp bhyt
    r"\b(gcn|xnv|xnsv)\b": ["Giấy chứng nhận", "Xác nhận sinh viên", "Xác nhận vay vốn"], # Đổi sv -> xnsv để tránh False Positive
}


def expand_query(query: str) -> str:
    """
    Mở rộng câu hỏi bằng cách dò tìm các từ viết tắt trong SYNONYM_DICT 
    và nối thêm các từ đồng nghĩa/mã ngành vào cuối câu hỏi.
    
    Điều này giúp thuật toán Sparse Vector (Lexical Search) có cơ hội bắt được 
    chính xác văn bản chứa tên đầy đủ hoặc mã ngành.
    """
    if not query:
        return query
        
    query_lower = query.lower()
    expansions = set()
    
    for pattern, synonyms in SYNONYM_DICT.items():
        if re.search(pattern, query_lower):
            expansions.update(synonyms)
            
    if expansions:
        # Nối thêm các từ khóa mở rộng vào cuối câu truy vấn
        expanded_text = " ".join(expansions)
        return f"{query} {expanded_text}"
        
    return query

def normalize_entity_name(text: str) -> str:
    """
    Chuẩn hóa tên ngành/chuyên ngành bằng cách thay thế trực tiếp các từ viết tắt 
    bằng tên chính thức (giá trị đầu tiên trong mảng đồng nghĩa).
    Ví dụ: 'Ngành IT' -> 'Ngành Công nghệ thông tin'
    """
    if not text:
        return text
        
    normalized_text = text
    for pattern, synonyms in SYNONYM_DICT.items():
        if synonyms:
            primary_name = synonyms[0]
            normalized_text = re.sub(pattern, primary_name, normalized_text, flags=re.IGNORECASE)
            
    # Xử lý thừa khoảng trắng nếu có
    return re.sub(r'\s+', ' ', normalized_text).strip()

