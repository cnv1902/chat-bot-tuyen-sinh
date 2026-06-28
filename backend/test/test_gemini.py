import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Load .env
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = os.getenv("GEMINI_MODEL")

if not API_KEY:
    print("❌ GOOGLE_API_KEY không được tìm thấy trong .env")
    sys.exit(1)

if not MODEL:
    print("❌ GEMINI_MODEL không được tìm thấy trong .env")
    sys.exit(1)

print(f"Model: {MODEL}")

try:
    genai.configure(api_key=API_KEY)

    model = genai.GenerativeModel(MODEL)

    print("Đang gửi request...")

    response = model.generate_content(
        "Hãy trả lời đúng một từ: OK",
        request_options={"timeout": 30},  # timeout 30 giây
    )

    print("\n===== RESPONSE =====")
    print(response.text)

except Exception as e:
    print("\n===== ERROR =====")
    print(type(e).__name__)
    print(e)