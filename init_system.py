import asyncio
import os
import sys
from typing import Sequence

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


# 确保可以从项目根目录导入 app 包
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401  # 确保所有模型被注册到 Base.metadata


async def check_database_connection(database_url: str) -> None:
    # 仅用于连通性检查
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("[DB] 数据库连接成功")
    except Exception as exc:
        print("[DB] 数据库连接失败，请检查配置：DATABASE_URL")
        print(f"[DB] 错误信息: {exc}")
        raise
    finally:
        await engine.dispose()


async def create_tables(database_url: str) -> None:
    # 创建扩展与表
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            print("[DB] 启用 pgvector 扩展...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            print("[DB] 创建数据表...")
            if not Base.metadata.tables:
                print("[DB] 警告：未发现任何 ORM 表结构（可能未导入 models）")
            await conn.run_sync(Base.metadata.create_all)
            print("[DB] 数据表创建完成")
    except Exception as exc:
        print("[DB] 创建数据表失败")
        print(f"[DB] 错误信息: {exc}")
        raise
    finally:
        await engine.dispose()


async def create_vector_index_if_needed(database_url: str) -> None:
    # 创建向量索引（可选）
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            print("[DB] 创建向量索引（若不存在）...")
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_std_vector_hnsw "
                    "ON standardvectorstore USING hnsw (embedding vector_cosine_ops) "
                    "WITH (m = 16, ef_construction = 64)"
                )
            )
            print("[DB] 向量索引检查完成")
    except Exception as exc:
        print("[DB] 创建向量索引失败（可忽略，但会影响向量检索性能）")
        print(f"[DB] 错误信息: {exc}")
        raise
    finally:
        await engine.dispose()


async def test_embedding_api(base_url: str, model: str, timeout_seconds: int) -> None:
    # 简单测试 Embedding API 是否可用
    payload = {"model": model, "input": "DSMS init test"}
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(f"{base_url}/v1/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            embedding = data["data"][0]["embedding"]
            if not isinstance(embedding, Sequence) or len(embedding) == 0:
                raise ValueError("Embedding 结果为空")
            if len(embedding) != 1024:
                raise ValueError(f"Embedding 维度不匹配，期望 1024，实际 {len(embedding)}")
        print("[EMB] Embedding API 可用")
    except Exception as exc:
        print("[EMB] Embedding API 不可用，请检查 LM Studio 配置或服务状态")
        print(f"[EMB] 错误信息: {exc}")
        raise


async def main() -> None:
    settings = get_settings()
    print("[INIT] 开始系统初始化")
    print(f"[INIT] DATABASE_URL={settings.database_url}")
    print(f"[INIT] LMSTUDIO_BASE_URL={settings.lmstudio_base_url}")
    print(f"[INIT] LMSTUDIO_EMBEDDING_MODEL={settings.lmstudio_embedding_model}")

    # 1. 检查数据库连通性
    await check_database_connection(settings.database_url)

    # 2. 创建表与索引
    await create_tables(settings.database_url)
    await create_vector_index_if_needed(settings.database_url)

    # 3. 测试 Embedding API
    await test_embedding_api(
        settings.lmstudio_base_url,
        settings.lmstudio_embedding_model,
        settings.lmstudio_timeout_seconds,
    )

    print("[INIT] 系统初始化完成")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # 已打印详细错误，这里仅设置退出码
        sys.exit(1)
