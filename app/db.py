from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


# ORM 基类
class Base(DeclarativeBase):
    pass


# 数据库引擎与会话工厂
settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# FastAPI 依赖注入：获取异步会话
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# 初始化数据库（创建扩展 + 表）
async def init_db() -> None:
    # 确保模型已注册到 Base.metadata
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        # 启用 pgvector 扩展
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
