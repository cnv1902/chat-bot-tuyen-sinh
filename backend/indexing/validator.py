"""
indexing/validator.py
=====================
Bước 3: Lớp kiểm duyệt Regex — Chặn ảo giác số liệu từ Gemini Vision.

Triết lý: Hệ thống tuyển sinh không thể sai số — một điểm chuẩn sai
có thể khiến thí sinh đưa ra quyết định sai lầm nghiêm trọng.
Validator là "guardrail" Regex đơn giản nhưng deterministic,
bắt các lỗi phổ biến nhất trước khi data vào Vector DB.

Khi validation thất bại:
- KHÔNG block pipeline — vẫn tiếp tục xử lý chunk đó
- Ghi nhận vào needs_review.json để admin kiểm tra thủ công
- Log cảnh báo rõ ràng để dễ tracing
"""

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ruleset — Mỗi rule là (pattern, validator_fn, rule_name, description)
# ---------------------------------------------------------------------------

def _check_score_range(match_str: str) -> tuple[bool, str]:
    """Điểm chuẩn phải nằm trong khoảng 10.0 - 30.0."""
    try:
        val = float(match_str.replace(",", "."))
        if not (10.0 <= val <= 30.0):
            return False, f"Điểm {val} nằm ngoài ngưỡng hợp lý [10, 30]"
        return True, ""
    except ValueError:
        return False, f"Không parse được điểm: {match_str!r}"


def _check_major_code_length(match_str: str) -> tuple[bool, str]:
    """Mã ngành theo chuẩn Bộ GD&ĐT phải đúng 7 chữ số."""
    digits = re.sub(r"\D", "", match_str)
    if len(digits) != 7:
        return False, f"Mã ngành '{match_str}' không phải 7 chữ số (tìm thấy {len(digits)})"
    return True, ""


def _check_tuition_range(match_str: str) -> tuple[bool, str]:
    """Học phí phải nằm trong ngưỡng hợp lý (triệu VNĐ/năm)."""
    try:
        # Bỏ dấu phân cách nghìn (1.500.000 → 1500000)
        clean = match_str.replace(".", "").replace(",", "")
        val = float(clean)
        # Học phí tính bằng VNĐ: 5 triệu → 100 triệu/năm là hợp lý
        if not (5_000_000 <= val <= 100_000_000):
            return False, f"Học phí {val:,.0f} VNĐ nằm ngoài ngưỡng hợp lý [5M, 100M]"
        return True, ""
    except ValueError:
        return False, f"Không parse được học phí: {match_str!r}"


# Cấu trúc rule: (regex_pattern, validator_function, rule_name)
_RULES: list[tuple[str, callable, str]] = [
    (
        # Điểm chuẩn — bắt số thập phân sau từ khóa
        r"(?:điểm\s*chuẩn|điểm\s*trúng\s*tuyển|điểm\s*sàn)[:\s=]+(\d{1,2}(?:[.,]\d{1,2})?)",
        _check_score_range,
        "diem_chuan_range",
    ),
    (
        # Mã ngành — số 7 chữ số đứng độc lập (word boundary)
        r"(?:mã\s*ngành|mã\s*số)[:\s]+(\b\d{5,8}\b)",
        _check_major_code_length,
        "ma_nganh_7digits",
    ),
    (
        # Học phí — số lớn kèm đơn vị VNĐ/đồng
        r"(?:học\s*phí|mức\s*thu)[:\s=]+(\d[\d.,]+)\s*(?:vnđ|đồng|vnd|d)?",
        _check_tuition_range,
        "hoc_phi_range",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_markdown(markdown: str, source_hint: str = "") -> dict:
    """
    Kiểm duyệt nội dung Markdown từ Gemini Vision bằng Regex deterministic.

    Quét toàn bộ nội dung với từng rule, thu thập tất cả vi phạm
    thay vì dừng ở vi phạm đầu tiên (fail-all strategy).

    Args:
        markdown:    Nội dung Markdown cần kiểm duyệt.
        source_hint: Mô tả nguồn (ví dụ: "page_3 of DeAn2026.pdf") để log rõ hơn.

    Returns:
        {
            "valid":  bool,      # True nếu KHÔNG có vi phạm nào
            "issues": list[dict] # Danh sách vi phạm chi tiết
        }

    Example output khi có vấn đề:
        {
            "valid": False,
            "issues": [
                {"rule": "diem_chuan_range", "value": "45.0",
                 "msg": "Điểm 45.0 nằm ngoài ngưỡng hợp lý [10, 30]"}
            ]
        }
    """
    if not markdown or not markdown.strip():
        return {"valid": True, "issues": []}

    issues: list[dict] = []

    for pattern, validator_fn, rule_name in _RULES:
        for match in re.finditer(pattern, markdown, re.IGNORECASE):
            matched_value = match.group(1).strip()
            is_valid, error_msg = validator_fn(matched_value)

            if not is_valid:
                issue = {
                    "rule":     rule_name,
                    "value":    matched_value,
                    "msg":      error_msg,
                    "context":  markdown[max(0, match.start()-30):match.end()+30].strip(),
                }
                issues.append(issue)
                logger.warning(
                    "[Validator] Vi phạm rule '%s' | %s | nguồn: %s",
                    rule_name, error_msg, source_hint or "unknown",
                )

    result = {"valid": len(issues) == 0, "issues": issues}

    if result["valid"]:
        logger.debug("[Validator] OK | %s", source_hint or "unknown")
    else:
        logger.warning(
            "[Validator] %d vi phạm phát hiện | %s",
            len(issues), source_hint or "unknown",
        )

    return result
