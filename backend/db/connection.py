"""
db/connection.py
================
SQLAlchemy async engine và session factory.
Dùng asyncpg driver cho PostgreSQL.

DATABASE_URL được đọc từ biến môi trường:
  - Khi chạy trong Docker: docker-compose.yml inject URL với hostname "postgres"
  - Khi chạy local:        .env cung cấp URL với hostname "localhost"
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://chatbot_user:chatbot_pass@localhost:5432/chatbot_db",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,    # Kiểm tra connection trước khi dùng, tránh lỗi stale
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class cho tất cả ORM models."""
    pass


async def get_db():
    """
    FastAPI dependency — yield async session, đảm bảo đóng sau request.

    Usage trong router:
        @router.get("/example")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Tạo tất cả tables từ ORM models.
    Idempotent — gọi nhiều lần không có tác dụng phụ.
    Gọi trong startup hook của FastAPI (api/main.py).
    """
    async with engine.begin() as conn:
        # Import models để SQLAlchemy biết cần tạo table nào
        from db import models  # noqa: F401 — import có side effect (register metadata)
        await conn.run_sync(Base.metadata.create_all)
