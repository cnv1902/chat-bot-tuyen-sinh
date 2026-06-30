from pathlib import Path
from markitdown import MarkItDown

# Khởi tạo converter
md = MarkItDown()

# File đầu vào
input_file = "Giới thiệu TDV.docx"

# Chuyển sang Markdown
result = md.convert(input_file)

# File đầu ra
output_file = "output.md"

# Ghi Markdown ra file
Path(output_file).write_text(
    result.text_content,
    encoding="utf-8"
)

print(f"Đã chuyển đổi thành công: {output_file}")