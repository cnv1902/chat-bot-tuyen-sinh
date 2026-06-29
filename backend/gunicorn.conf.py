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
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000       # Số connections đồng thời tối đa mỗi worker

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = 120           # Request timeout (giây) — OCR pipeline có thể tốn 60-100s
keepalive = 5           # Keep-alive connections
graceful_timeout = 30   # Thời gian chờ worker hoàn tất request trước khi kill

# ---------------------------------------------------------------------------
# PRELOAD APP
# ---------------------------------------------------------------------------
# preload_app = False (Mặc định của Gunicorn):
#
# VIỆC DÙNG preload_app=True ĐÃ ĐƯỢC XÁC NHẬN LÀ DEADLOCK VỚI BEG-M3:
# HọC thực `sentence-transformers` dùng thư viện `tokenizers` viết bằng Rust.
# Khi load model, Rust runtime tạo các thread nền (background thread). Nếu
# Gunicorn fork() trong khi thread đang tồn tại, mutex của Rust runtime
# sẽ bị khóa vĩnh viễn trong worker con (fork-after-thread deadlock).
#
# GIẢI PHÁP: Để preload_app=False. Mỗi worker tự import app và chạy lifespan
# SAU KHI đã fork xong. Lúc này không có thread nào tồn tại khi fork,
# nên hoàn toàn an toàn. Mỗi worker sẽ load model một lần riêng.
#
# VÈ RAM: với bge-m3 ~570MB/worker và RAM 7.3GB:
#   - 2 workers: ~1.1GB model + app overhead → AN TOÀN
#   - 4 workers: ~2.3GB model + overhead   → CÓTHỂ TIGHT
# Mặc định 2, override qua GUNICORN_WORKERS nếu server có nhiều RAM hơn.
preload_app = False

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
    """Gọi khi master process khởi động (trước khi fork)."""
    server.log.info(
        "[Gunicorn] Master khởi động. preload_app=False — model sẽ được "
        "load trong từng worker sau fork để tránh fork-after-thread deadlock."
    )


def post_fork(server, worker):
    """Gọi TRONG TỪNG worker SAU KHI fork — dùng để reset các resource không fork-safe."""
    server.log.info(f"[Gunicorn] Worker {worker.pid} đã fork từ master.")


def worker_exit(server, worker):
    """Gọi khi worker thoát — dùng để cleanup resource nếu cần."""
    server.log.info(f"[Gunicorn] Worker {worker.pid} đã dừng.")
