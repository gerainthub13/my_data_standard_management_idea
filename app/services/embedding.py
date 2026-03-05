from __future__ import annotations

import asyncio
import uuid
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models import DataStandard, StandardVectorStore


settings = get_settings()


# 将标准信息拼接为向量生成的源文本
def build_sourcecontent(standard: DataStandard) -> str:
    parts: list[str] = [standard.name]
    if standard.description:
        parts.append(standard.description)
    if standard.extattributes:
        for key, value in standard.extattributes.items():
            parts.append(f"{key}:{value}")
    return "\n".join(parts)


# 调用 LM Studio Embedding 接口
async def fetch_embedding(text: str) -> list[float]:
    payload = {"model": settings.lmstudio_embedding_model, "input": text}
    async with httpx.AsyncClient(timeout=settings.lmstudio_timeout_seconds) as client:
        resp = await client.post(f"{settings.lmstudio_base_url}/v1/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
    embedding = data["data"][0]["embedding"]
    # 与库表维度一致（1024）
    if len(embedding) != 1024:
        raise ValueError(f"Embedding 维度不匹配，期望 1024，实际 {len(embedding)}")
    return embedding


# 写入或更新向量
async def upsert_embedding(
    session: AsyncSession,
    standard: DataStandard,
    lang: str,
) -> None:
    sourcecontent = build_sourcecontent(standard)
    embedding = await fetch_embedding(sourcecontent)

    stmt = select(StandardVectorStore.id).where(
        StandardVectorStore.refid == standard.id,
        StandardVectorStore.lang == lang,
        StandardVectorStore.modelname == settings.lmstudio_embedding_model,
    )
    result = await session.execute(stmt)
    existing_id = result.scalar_one_or_none()

    if existing_id:
        await session.execute(
            StandardVectorStore.__table__.update()
            .where(StandardVectorStore.id == existing_id)
            .values(
                sourcecontent=sourcecontent,
                embedding=embedding,
            )
        )
    else:
        session.add(
            StandardVectorStore(
                refid=standard.id,
                lang=lang,
                modelname=settings.lmstudio_embedding_model,
                sourcecontent=sourcecontent,
                embedding=embedding,
            )
        )


# 在独立会话中重建指定标准的向量
async def rebuild_embedding_for_standard(standard_id: str, lang: str) -> None:
    try:
        standard_uuid = uuid.UUID(standard_id)
    except ValueError:
        return

    async with AsyncSessionLocal() as session:
        stmt = select(DataStandard).where(
            DataStandard.id == standard_uuid,
            DataStandard.is_deleted == False,
        )
        result = await session.execute(stmt)
        standard = result.scalar_one_or_none()
        if not standard:
            return
        await upsert_embedding(session, standard, lang)
        await session.commit()


# 在当前事件循环中安排异步任务（或直接运行）
def schedule_embedding_rebuild(standard_id: str, lang: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(rebuild_embedding_for_standard(standard_id, lang))
    except RuntimeError:
        asyncio.run(rebuild_embedding_for_standard(standard_id, lang))
