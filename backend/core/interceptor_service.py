"""
core/interceptor_service.py
===========================
Dịch vụ tiền xử lý chặn các câu hỏi độc hại hoặc câu chào đơn giản,
giúp giảm tải gọi LLM không cần thiết và bảo vệ hệ thống.
"""

import random
import logging
from rapidfuzz import process, fuzz

logger = logging.getLogger(__name__)

# Danh sách từ khóa độc hại, nhạy cảm
BLACKLIST_WORDS = [
    "đặt bom", "khủng bố", "chửi", "lừa đảo", "giết", "tự tử",
    "đụ", "địt", "đm", "vkl", "cặc", "lồn",
    "phá hoại", "hack", "ddos"
]

# Danh sách template câu chào để so khớp (Fuzzy match)
GREETING_TEMPLATES = [
    "xin chào", "chào bạn", "hi", "hello", "alo",
    "chào ad", "chào cậu", "chào", "chào buổi sáng", "chào buổi chiều"
]

# Danh sách phản hồi cho câu chào
GREETING_RESPONSES = [
    "Chào bạn, mình là Trợ lý AI tư vấn tuyển sinh của ĐH Vinh. Mình có thể giúp gì cho bạn hôm nay?",
    "Xin chào! Bạn đang quan tâm đến thông tin tuyển sinh nào của ĐH Vinh?",
    "Chào bạn! Rất vui được hỗ trợ bạn. Bạn cần tìm hiểu thông tin về ngành học hay điểm chuẩn?",
    "Dạ chào bạn. Bạn cứ đặt câu hỏi, mình sẽ giải đáp thông tin tuyển sinh chi tiết nhé.",
    "Chào bạn. Mình là AI tuyển sinh. Bạn muốn biết thêm về cách xét tuyển hay các ngành đào tạo ạ?",
]

def check_interceptor(user_query: str) -> str | None:
    """
    Kiểm tra câu hỏi của user:
    - Nếu chứa từ khóa độc hại -> Trả về câu từ chối.
    - Nếu là câu chào ngắn gọn -> Trả về câu chào ngẫu nhiên.
    - Nếu bình thường -> Trả về None để đi tiếp vào Agent.
    """
    if not user_query:
        return None
        
    query_lower = user_query.lower()
    
    # 1. Kiểm tra Blacklist (Toxic)
    for word in BLACKLIST_WORDS:
        if word in query_lower:
            logger.warning(f"[Interceptor] Phát hiện từ khóa độc hại '{word}' trong câu hỏi.")
            return "Xin lỗi, câu hỏi của bạn chứa từ ngữ không phù hợp. Vui lòng đặt câu hỏi lịch sự và liên quan đến tuyển sinh Đại học Vinh."

    # 2. Kiểm tra Greeting (Fuzzy Match nếu ngắn)
    words = query_lower.split()
    if len(words) < 15:
        # Dùng rapidfuzz extractOne
        match = process.extractOne(
            query_lower, 
            GREETING_TEMPLATES, 
            scorer=fuzz.ratio
        )
        
        # match trả về tuple: (matched_string, score, index)
        if match and match[1] > 80:
            logger.info(f"[Interceptor] Intercepted by Greeting: '{user_query}' (matched '{match[0]}' with score {match[1]:.1f})")
            return random.choice(GREETING_RESPONSES)
            
    return None
