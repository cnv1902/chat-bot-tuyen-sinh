"""
api/main.py
===========
Điểm khởi động chính của FastAPI Application — Chatbot Tuyển sinh ĐH Vinh.

Chịu trách nhiệm:
    [1] Load biến môi trường từ .env
    [2] Cấu hình logging chuẩn hóa cho toàn project
    [3] Khởi tạo FastAPI app với metadata OpenAPI
    [4] Cấu hình CORS (đọc từ env, hỗ trợ nhiều origin)
    [5] Đăng ký exception handlers toàn cục
    [6] Include API routers (chat + health)
    [7] Mount thư mục frontend/ làm static files
    [8] Startup/Shutdown event hooks:
        - Startup: warmup embedding model + tạo Qdrant collection nếu chưa có
        - Shutdown: log thông báo tắt sạch

Khởi chạy:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import logging.config
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# [1] Load .env trước khi import bất kỳ module nào đọc os.getenv()
# ---------------------------------------------------------------------------
# Tìm .env từ thư mục gốc project (2 cấp lên từ api/main.py)
_ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_ROOT_DIR / ".env", override=False)
# override=False: biến đã có trong shell environment sẽ được giữ nguyên
# (hành vi chuẩn cho deployment với CI/CD inject secrets qua env vars)

# ---------------------------------------------------------------------------
# [2] Cấu hình Logging
# ---------------------------------------------------------------------------
# Thiết lập trước khi bất kỳ logger nào được sử dụng

def _setup_logging() -> None:
    """Cấu hình logging format chuẩn hóa cho toàn project và lưu ra file."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_format = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Đảm bảo thư mục logs tồn tại
    log_dir = _ROOT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # Ghi log ra cả Console và File
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8")
    ]

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
    )

    # Giảm noise từ các thư viện verbose
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    logging.getLogger("google.generativeai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import sau khi đã load .env và setup logging
# ---------------------------------------------------------------------------
from api.routers import chat as chat_router
from api.routers import health as health_router
from api.routers import upload as upload_router
from api.routers import admin as admin_router
from api.routers import auth as auth_router
from api.routers import auth_google as auth_google_router
from api.routers import academic as academic_router
from api.routers import admission as admission_router
from api.routers import admission_crud as admission_crud_router
from api.routers import staff as staff_router
from api.routers import candidate_router
from api.schemas import ErrorResponse
from core.embedder import warmup as embedder_warmup
from core.vectordb import setup_collection


# ---------------------------------------------------------------------------
# Seed LLM config mặc định
# ---------------------------------------------------------------------------

async def _seed_default_llm_config() -> None:
    """
    Seed cấu hình Gemini mặc định vào DB nếu chưa có dữ liệu.
    Idempotent — gọi nhiều lần không có tác dụng phụ.
    Credentials được đọc từ biến môi trường hiện tại.
    """
    import os
    from db.connection import AsyncSessionLocal
    from db.crud import get_slot, upsert_provider, upsert_slot

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.warning("[Seed] GOOGLE_API_KEY chưa được thiết lập — bỏ qua seed Gemini.")
        return

    async with AsyncSessionLocal() as db:
        # Chỉ seed nếu chưa có slot "chat" (tức là DB mới khởi tạo)
        existing = await get_slot(db, "chat")
        if existing:
            logger.info("[Seed] DB đã có dữ liệu — bỏ qua seed mặc định.")
            return

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        await upsert_provider(db, "gemini", api_key=api_key, is_active=True)
        await upsert_slot(db, "chat", "gemini", model_name)
        await upsert_slot(db, "ocr",  "gemini", model_name)
        logger.info(
            "[Seed] \u2705 Seed xong: provider=gemini, model=%s, slots=[chat, ocr]",
            model_name,
        )

async def _seed_admin_account() -> None:
    from sqlalchemy import select
    from db.connection import AsyncSessionLocal
    from db.models import Account, RoleEnum
    from api.routers.auth import get_password_hash
    
    async with AsyncSessionLocal() as db:
        stmt = select(Account).where(Account.username == "admin")
        result = await db.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if not admin:
            hashed_pw = get_password_hash("admin")
            new_admin = Account(
                username="admin",
                password_hash=hashed_pw,
                role=RoleEnum.ADMIN,
                is_active=True
            )
            db.add(new_admin)
            await db.commit()
            logger.info("[Seed] \u2705 Đã tạo tài khoản admin mặc định.")

# ---------------------------------------------------------------------------
# [8] Lifespan Context Manager (thay thế on_event deprecated trong FastAPI 0.93+)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Quản lý vòng đời ứng dụng.

    STARTUP (trước khi nhận request):
        1. Warmup embedding model → tải BAAI/bge-m3 vào RAM
           (tránh cold start lag ~5-8s ở request đầu tiên)
        2. Đảm bảo Qdrant collection tồn tại
           (idempotent — an toàn khi restart nhiều lần)

    SHUTDOWN (sau khi stop nhận request):
        - Log thông báo tắt sạch để dễ phân biệt restart vs crash trong log
    """
    # ── STARTUP ──
    logger.info("=" * 60)
    logger.info("🚀 CHATBOT TUYỂN SINH ĐH VINH — ĐANG KHỜI ĐỘNG")
    logger.info("=" * 60)

    # [0] Khởi tạo PostgreSQL tables + seed config mặc định
    logger.info("[Startup] [0/3] Khởi tạo PostgreSQL database...")
    try:
        from db.connection import init_db
        await init_db()
        logger.info("[Startup] [0/3] PostgreSQL tables ✅ sẵn sàng.")

        # Seed config Gemini mặc định nếu DB còn rỗng
        await _seed_default_llm_config()
        # Seed tài khoản admin mặc định
        await _seed_admin_account()
    except Exception as e:
        logger.error("[Startup] [0/3] Lỗi PostgreSQL: %s", str(e))
        logger.warning("[Startup] Chat sẽ dùng Gemini hardcode nếu DB không khả dụng.")

    # Warmup embedding model (blocking — intentional để request đầu không lag)
    logger.info("[Startup] [1/3] Warmup embedding model...")
    try:
        embedder_warmup()   # Hàm này đã có try/except nội bộ — không raise
        logger.info("[Startup] [1/3] Embedding model ✅ sẵn sàng.")
    except Exception as e:
        # Không block startup — API vẫn lên, lỗi embed sẽ xảy ra khi có request
        logger.error("[Startup] [1/3] Warmup embedder thất bại: %s", str(e))

    # Đảm bảo Qdrant collection tồn tại
    logger.info("[Startup] [2/3] Kiểm tra Qdrant collection...")
    try:
        collection_ok = setup_collection()
        if collection_ok:
            logger.info(
                "[Startup] [2/3] Qdrant collection '%s' ✅ sẵn sàng.",
                os.getenv("QDRANT_COLLECTION", "tuyen_sinh_dhv"),
            )
        else:
            logger.warning(
                "[Startup] [2/3] Không thể tạo/xác nhận Qdrant collection. "
                "Search sẽ thất bại cho đến khi vấn đề được khắc phục."
            )
    except Exception as e:
        logger.error("[Startup] [2/3] Lỗi Qdrant: %s", str(e))

    logger.info("=" * 60)
    logger.info("✅ API SẴN SÀNG PHỤC VỤ | http://0.0.0.0:%s", os.getenv("API_PORT", "8000"))
    logger.info("=" * 60)

    yield  # ← Ứng dụng đang chạy và phục vụ requests

    # ── SHUTDOWN ──
    logger.info("=" * 60)
    logger.info("🛑 CHATBOT TUYỂN SINH ĐH VINH — ĐANG TẮT (graceful shutdown)")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# [3] Khởi tạo FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Chatbot Tuyển sinh Đại học Vinh",
    description=(
        "API hỗ trợ tư vấn tuyển sinh tự động cho Trường Đại học Vinh. "
        "Sử dụng kiến trúc Agentic RAG với LangGraph + Gemini 1.5 Flash + Qdrant.\n\n"
        "**Endpoint chính:** `POST /api/chat`\n\n"
        "**Health check:** `GET /health`"
    ),
    version="1.0.0",
    contact={
        "name":  "Phòng CNTT — Đại học Vinh",
        "url":   "https://vinhuni.edu.vn",
        "email": "cntt@vinhuni.edu.vn",
    },
    license_info={
        "name": "Internal Use Only",
    },
    lifespan=lifespan,
    # Tắt docs trong production để giảm attack surface
    # docs_url=None if os.getenv("ENV") == "production" else "/docs",
    # redoc_url=None if os.getenv("ENV") == "production" else "/redoc",
)


# ---------------------------------------------------------------------------
# [4] CORS Middleware
# ---------------------------------------------------------------------------

def _parse_cors_origins() -> list[str]:
    """
    Đọc danh sách CORS origins từ biến môi trường.
    Hỗ trợ nhiều origins phân cách bằng dấu phẩy.

    Ví dụ .env:
        CORS_ORIGINS=http://localhost:3000,https://tuyensinh.vinhuni.edu.vn

    Returns:
        ["http://localhost:3000", "https://tuyensinh.vinhuni.edu.vn"]
    """
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").strip()
    origins = [o.strip() for o in raw.split(",") if o.strip()]

    logger.info("[CORS] Cho phép origins: %s", origins)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,          # Cho phép cookie/Authorization header
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],   # Cho phép các method cần thiết bao gồm DELETE cho quản lý tài liệu
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",              # Custom header cho request tracing
    ],
    expose_headers=["X-Request-ID"], # Cho phép client đọc header này từ response
    max_age=3600,                    # Cache preflight response 1 giờ
)


# ---------------------------------------------------------------------------
# [5] Global Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Bắt tất cả unhandled exception — tránh leak traceback ra client.
    Log đầy đủ nội bộ để debug, trả về response sạch cho client.
    """
    logger.critical(
        "[Exception] Unhandled exception tại %s %s: %s",
        request.method,
        request.url.path,
        str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_server_error",
            detail="Hệ thống gặp sự cố không mong muốn. Vui lòng thử lại sau.",
        ).model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Xử lý ValueError (thường từ validation logic thủ công)."""
    logger.warning(
        "[Exception] ValueError tại %s: %s", request.url.path, str(exc)
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error="bad_request",
            detail=str(exc),
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# [6] Include Routers
# ---------------------------------------------------------------------------

app.include_router(chat_router.router)     # POST /api/chat
app.include_router(health_router.router)   # GET /health
app.include_router(upload_router.router)   # POST /api/upload
app.include_router(admin_router.router)    # GET/POST /admin/*
app.include_router(auth_router.router)     # POST /api/auth/login
app.include_router(auth_google_router.router) # POST /api/auth/google
app.include_router(academic_router.router) # POST/GET /api/academic/*
app.include_router(admission_router.router) # POST/GET /api/admission/*
app.include_router(admission_crud_router.router) # CRUD /api/admission_crud/*
app.include_router(staff_router.router)    # CRUD /api/staff/*
app.include_router(candidate_router.router) # CRUD /api/candidate/*

logger.info("[Router] Đã đăng ký: POST /api/chat | GET /health | /admin/* | /api/auth/* | /api/academic/* | /api/admission/*")


# ---------------------------------------------------------------------------
# [7] Mount Static Files (Frontend Widget)
# ---------------------------------------------------------------------------

_FRONTEND_DIR = _ROOT_DIR / "frontend"

if _FRONTEND_DIR.exists() and _FRONTEND_DIR.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(_FRONTEND_DIR)),
        name="static",
    )
    logger.info("[Static] Frontend widget mounted tại /static → %s", _FRONTEND_DIR)
else:
    logger.warning(
        "[Static] Thư mục frontend/ không tồn tại tại %s. "
        "Static files KHÔNG được mount. "
        "Tạo thư mục và chạy lại nếu cần serve widget.",
        _FRONTEND_DIR,
    )


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    """
    Root endpoint — trả về thông tin API cơ bản.
    Hữu ích để confirm server đang chạy khi kiểm tra bằng browser.
    """
    return JSONResponse(
        content={
            "service":  "Chatbot Tuyển sinh Đại học Vinh",
            "version":  "1.0.0",
            "status":   "running",
            "docs":     "/docs",
            "health":   "/health",
            "chat_api": "/api/chat",
        }
    )


# ---------------------------------------------------------------------------
# Entry point khi chạy trực tiếp (dev mode)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,          # Hot-reload khi sửa code (chỉ dùng trong dev)
        reload_excludes=["logs/*", "*.log", "*.db", "*.sqlite3"],
        log_level="info",
        access_log=True,
    )
