# ==============================================================================
# Dockerfile cho FastAPI Backend
# Sử dụng base image Debian mỏng nhẹ (slim) có sẵn Python 3.11
# ==============================================================================

FROM python:3.11-slim

# Ngăn chặn Python tạo file .pyc và ép stdout không bị buffer (tốt cho logging)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cài đặt các thư viện hệ thống, ĐẶC BIỆT là poppler-utils để xử lý PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Sao chép file requirements.txt và cài đặt dependency trước
# (Lợi dụng Docker cache layer để không phải cài lại package nếu requirements không đổi)
COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Khởi tạo trước cache directory cho HuggingFace để Embedding Model có thể download offline (tuỳ chọn)
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface

# Sao chép toàn bộ mã nguồn backend vào container
COPY . .

# Expose port 8000 để docker-compose có thể bind
EXPOSE 8000

# Lệnh khởi chạy server (có thể bị ghi đè bởi docker-compose tùy môi trường dev/prod)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
