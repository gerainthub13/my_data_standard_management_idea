from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import DataStandard
from app.schemas import EmbeddingRebuildOut, EmbeddingRebuildRequest
from app.services.embedding import schedule_embedding_rebuild


# Embedding 管理 API
router = APIRouter(prefix="/api/v1/embeddings", tags=["embeddings"])
settings = get_settings()


@router.post(
    "/rebuild",
    response_model=EmbeddingRebuildOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="重建向量",
    description="支持指定标准 ID 列表或全量重建。接口会返回 accepted/skipped/warnings 方便调用方判断结果。",
)
async def rebuild_embeddings(
    payload: EmbeddingRebuildRequest,
    session: AsyncSession = Depends(get_session),
):
    warnings: list[str] = []

    # 指定标准重建
    if payload.refids:
        stmt = select(DataStandard.id).where(
            DataStandard.id.in_(payload.refids),
            DataStandard.is_deleted == False,
        )
        result = await session.execute(stmt)
        existing_ids = {row[0] for row in result.all()}
        skipped_ids = [str(refid) for refid in payload.refids if refid not in existing_ids]

        for refid in existing_ids:
            schedule_embedding_rebuild(str(refid), payload.lang or settings.default_language)
        if skipped_ids:
            warnings.append(f"以下标准不存在或已删除，已跳过：{', '.join(skipped_ids)}")

        return EmbeddingRebuildOut(
            accepted=len(existing_ids),
            skipped=len(skipped_ids),
            warnings=warnings,
        )

    # 全量重建
    stmt = select(DataStandard.id).where(DataStandard.is_deleted == False)
    result = await session.execute(stmt)
    ids = [row[0] for row in result.all()]
    for refid in ids:
        schedule_embedding_rebuild(str(refid), payload.lang or settings.default_language)
    return EmbeddingRebuildOut(accepted=len(ids), skipped=0, warnings=warnings)
