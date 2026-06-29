# ==============================================================================
# gunicorn.conf.py — Cấu hình Gunicorn cho Production
# ==============================================================================
# Tài liệu: https://docs.gunicorn.org/en/stable/settings.html
#
# Lý do dùng file config thay vì truyền CLI args:
# - Dễ đọc, dễ version control
# - Hỗ trợ hooks (pre_fork, post_fork, worker_exit...)
# - Không bị giới hạn bởi độ dài dòng lệnh
# ==============================================================================

import multiprocessing
import os

# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------
bind = "0.0.0.0:8000"

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
# Số worker = 2 × CPU cores + 1 là quy tắc phổ biến cho I/O-bound workloads.
# Với container giới hạn 4 CPUs, mặc định là 4 workers.
# Override qua biến môi trường GUNICORN_WORKERS nếu cần.
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000       # Số connections đồng thời tối đa mỗi worker

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = 120           # Request timeout (giây) — OCR pipeline có thể tốn 60-100s
keepalive = 5           # Keep-alive connections
graceful_timeout = 30   # Thời gian chờ worker hoàn tất request trước khi kill

# ---------------------------------------------------------------------------
# PRELOAD APP — Giải quyết vấn đề load model 4 lần
# ---------------------------------------------------------------------------
# preload_app = True: Gunicorn sẽ import và khởi tạo ứng dụng trong process
# master TRƯỚC KHI fork các worker. Nhờ đó:
#   1. Embedding model (BAAI/bge-m3 ~570MB) chỉ load MỘT LẦN trong master.
#   2. Các worker con thừa kế bộ nhớ của master qua cơ chế Copy-on-Write (COW)
#      của Linux → tiết kiệm đáng kể RAM và thời gian khởi động.
#   3. Startup event (lifespan) của FastAPI vẫn chạy trong từng worker riêng
#      để khởi tạo các async resource (DB pool, Redis...) không thể share qua fork.
#
# LƯU Ý: Các kết nối DB/Redis KHÔNG được tạo ở module level (chỉ trong lifespan)
# vì file descriptors không share an toàn qua fork. Code hiện tại đã đúng chuẩn này.
preload_app = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Gunicorn ghi access log và error log riêng. "-" = stdout (Docker best practice)
accesslog = "-"
errorlog = "-"
loglevel = "warning"    # Giảm noise từ Gunicorn, app log vẫn dùng logging riêng
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ---------------------------------------------------------------------------
# Process Naming
# ---------------------------------------------------------------------------
proc_name = "chatbot_tuyensinh"
default_proc_name = "chatbot_tuyensinh"


# ---------------------------------------------------------------------------
# Server Hooks — Lifecycle callbacks
# ---------------------------------------------------------------------------

def on_starting(server):
    """Gọi khi master process khởi động. Model sẽ được load tại đây."""
    server.log.info("[Gunicorn] Master process đang khởi động. preload_app=True.")


def post_fork(server, worker):
    """Gọi TRONG TỪNG worker SAU KHI fork — dùng để reset các resource không fork-safe."""
    server.log.info(f"[Gunicorn] Worker {worker.pid} đã fork từ master.")


def worker_exit(server, worker):
    """Gọi khi worker thoát — dùng để cleanup resource nếu cần."""
    server.log.info(f"[Gunicorn] Worker {worker.pid} đã dừng.")
