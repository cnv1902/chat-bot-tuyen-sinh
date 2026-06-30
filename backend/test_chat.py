import requests
import json
import time

def test_chat(message):
    start = time.time()
    res = requests.post(
        "http://localhost:8000/api/chat",
        json={"message": message}
    )
    end = time.time()
    print(f"[{end-start:.3f}s] {message} -> {res.status_code}")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    print("-" * 40)

if __name__ == "__main__":
    test_chat("Chào bạn")
    test_chat("Cho mình hỏi điểm chuẩn ngành công nghệ thông tin 2026")
    test_chat("Trường có ký túc xá cho sinh viên không?")
