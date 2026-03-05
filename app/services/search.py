from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataStandard, StandardVectorStore
from app.services.embedding import fetch_embedding


# 向量检索（cosine distance）
async def vector_search(
    session: AsyncSession,
    query: str,
    lang: str,
    top_k: int,
    status: int | None,
    is_latest: bool | None,
) -> list[tuple[DataStandard, float]]:
    query_vec = await fetch_embedding(query)
    distance = StandardVectorStore.embedding.cosine_distance(query_vec)
    filters = [
        DataStandard.is_deleted == False,
        StandardVectorStore.lang == lang,
    ]
    if status is not None:
        filters.append(DataStandard.status == status)
    if is_latest is not None:
        filters.append(DataStandard.is_latest == is_latest)

    stmt = (
        select(DataStandard, distance.label("distance"))
        .join(StandardVectorStore, StandardVectorStore.refid == DataStandard.id)
        .where(*filters)
        .order_by(distance.asc())
        .limit(top_k)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [(row[0], row[1]) for row in rows]


# 关键词过滤（ILIKE）
async def keyword_filter(
    session: AsyncSession,
    query: str,
    top_k: int,
    status: int | None,
    is_latest: bool | None,
) -> list[DataStandard]:
    filters = [
        DataStandard.is_deleted == False,
        (
            DataStandard.code.ilike(f"%{query}%")
            | DataStandard.name.ilike(f"%{query}%")
            | DataStandard.description.ilike(f"%{query}%")
        ),
    ]
    if status is not None:
        filters.append(DataStandard.status == status)
    if is_latest is not None:
        filters.append(DataStandard.is_latest == is_latest)

    stmt = (
        select(DataStandard)
        .where(*filters)
        .order_by(DataStandard.code)
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
