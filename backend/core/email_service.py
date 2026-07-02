"""
core/email_service.py
=====================
Xử lý việc tạo, lưu trữ và gửi mã OTP qua email (sử dụng Brevo).
"""

import os
import random
import logging
import httpx
from core.session import _get_client

logger = logging.getLogger(__name__)

# Constants
OTP_TTL_SECONDS = 300  # 5 phút
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "no-reply@vinhuni.edu.vn")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Hệ thống Tuyển sinh")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

def generate_and_store_otp(email: str) -> str:
    """
    Sinh mã OTP 6 số và lưu vào Redis.
    """
    otp_code = str(random.randint(100000, 999999))
    redis_key = f"otp:{email}"
    try:
        client = _get_client()
        # Lưu key với thời gian hết hạn TTL
        client.setex(redis_key, OTP_TTL_SECONDS, otp_code)
        logger.info(f"Đã tạo và lưu OTP cho email {email} (TTL: {OTP_TTL_SECONDS}s)")
        return otp_code
    except Exception as e:
        logger.error(f"Lỗi khi lưu OTP vào Redis cho {email}: {e}")
        # Trong trường hợp Redis sập, có thể fallback lưu ở memory tạm hoặc raise error
        raise e

def verify_otp_from_redis(email: str, otp_code: str) -> bool:
    """
    So khớp mã OTP. Nếu đúng, xóa key.
    """
    redis_key = f"otp:{email}"
    try:
        client = _get_client()
        stored_otp = client.get(redis_key)
        
        if stored_otp and stored_otp.decode("utf-8") == otp_code:
            # Xóa OTP sau khi verify thành công (chỉ dùng 1 lần)
            client.delete(redis_key)
            return True
        return False
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra OTP từ Redis cho {email}: {e}")
        return False

async def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Gửi email chứa OTP qua Brevo API.
    """
    if not BREVO_API_KEY:
        logger.warning("BREVO_API_KEY chưa được cấu hình. In OTP ra console thay vì gửi email.")
        logger.info(f"=== OTP CHO {email}: {otp_code} ===")
        return True

    payload = {
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": email}],
        "subject": "Mã xác thực Đăng nhập Hệ thống Tuyển sinh",
        "htmlContent": f"""
        <html>
            <body>
                <h2>Mã Xác Thực (OTP)</h2>
                <p>Chào bạn,</p>
                <p>Mã xác thực đăng nhập lần đầu của bạn là: <strong>{otp_code}</strong></p>
                <p>Mã này sẽ hết hạn trong vòng 5 phút.</p>
                <p>Trân trọng,<br/>Đội ngũ Hỗ trợ</p>
            </body>
        </html>
        """
    }

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(BREVO_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Đã gửi email OTP thành công tới {email}")
            return True
    except Exception as e:
        logger.error(f"Lỗi khi gửi email OTP tới {email} qua Brevo: {e}")
        return False
