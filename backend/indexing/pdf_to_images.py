"""
indexing/pdf_to_images.py
=========================
Bước 1: Chuyển đổi PDF → chuỗi ảnh JPEG.

Yêu cầu hệ thống: poppler-utils phải được cài đặt.
    Windows: chown poppler và thêm vào PATH
    Linux:   apt-get install -y poppler-utils
"""

import logging
from pathlib import Path

from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


def pdf_to_images(
    pdf_path: str,
    output_dir: str = "./tmp_images",
    dpi: int = 200,
) -> list[str]:
    """
    Chuyển đổi từng trang PDF thành file JPEG riêng biệt.

    Chọn 200dpi vì:
    - Đủ rõ để Gemini Vision nhận diện văn bản và bảng biểu
    - Không quá nặng (trung bình ~200-400KB/trang) → giảm chi phí API
    - Tốc độ xử lý cân bằng giữa chất lượng và tài nguyên

    Args:
        pdf_path:   Đường dẫn tới file PDF/Word cần xử lý.
        output_dir: Thư mục lưu ảnh JPEG đầu ra.
        dpi:        Độ phân giải (dots per inch). Mặc định 200.

    Returns:
        Danh sách đường dẫn file JPEG theo thứ tự trang.

    Raises:
        FileNotFoundError: Nếu pdf_path không tồn tại.
        RuntimeError:      Nếu poppler chưa được cài đặt.
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {pdf_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[PDF→IMG] Xử lý: %s | dpi=%d", pdf.name, dpi)

    try:
        pages = convert_from_path(str(pdf), dpi=dpi, fmt="jpeg")
    except Exception as e:
        raise RuntimeError(
            f"Lỗi convert PDF (kiểm tra poppler-utils): {e}"
        ) from e

    saved: list[str] = []
    for i, page in enumerate(pages):
        # Đặt tên file theo tên PDF gốc + số trang để tránh xung đột khi xử lý nhiều PDF
        out_path = out_dir / f"{pdf.stem}_page_{i + 1:03d}.jpg"
        page.save(str(out_path), "JPEG", quality=85)
        saved.append(str(out_path))

    logger.info("[PDF→IMG] Hoàn thành: %d trang → %s", len(saved), output_dir)
    return saved
