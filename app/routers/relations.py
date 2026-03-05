import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import build_api_error
from app.models import DataStandard, StandardRelation
from app.schemas import RelationCreate, RelationOut


# 关系管理 API
router = APIRouter(prefix="/api/v1/standards", tags=["relations"])


@router.post(
    "/{standard_id}/relations",
    response_model=RelationOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建标准关系",
    description="创建前会校验源标准存在性，并校验关键字段组合唯一。",
)
async def create_relation(
    standard_id: uuid.UUID,
    payload: RelationCreate,
    session: AsyncSession = Depends(get_session),
):
    standard_id_str = str(standard_id)

    # 校验源标准是否存在且未删除
    stmt = select(DataStandard.id).where(
        DataStandard.id == standard_id,
        DataStandard.is_deleted == False,
    )
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="源标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    # 防止重复关系写入（关键字段组合唯一）
    duplicate_stmt = select(StandardRelation.id).where(
        StandardRelation.sourceid == standard_id_str,
        StandardRelation.targetid == payload.targetid,
        StandardRelation.targetver == payload.targetver,
        StandardRelation.reltype == payload.reltype,
        StandardRelation.targettype == payload.targettype,
    )
    duplicate_id = (await session.execute(duplicate_stmt)).scalar_one_or_none()
    if duplicate_id:
        raise build_api_error(
            status_code=409,
            code="RELATION_ALREADY_EXISTS",
            message="关系已存在，无需重复创建",
            errors=[{"field": "relation", "message": "source-target-reltype 组合重复"}],
            warnings=[],
        )

    relation = StandardRelation(
        sourceid=standard_id_str,
        sourcever=None,
        targetid=payload.targetid,
        targetver=payload.targetver,
        reltype=payload.reltype,
        targettype=payload.targettype,
        relstatus=payload.relstatus,
    )
    session.add(relation)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="RELATION_CREATE_CONFLICT",
            message="关系创建失败：唯一约束冲突",
            errors=[{"field": "relation", "message": "请勿重复提交相同关系"}],
            warnings=[],
        )

    await session.refresh(relation)
    return relation


@router.get(
    "/{standard_id}/relations",
    response_model=list[RelationOut],
    summary="查询标准关系",
    description="返回指定标准的出入度关系记录。",
)
async def list_relations(
    standard_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    standard_id_str = str(standard_id)
    exists_stmt = select(DataStandard.id).where(
        DataStandard.id == standard_id,
        DataStandard.is_deleted == False,
    )
    exists = (await session.execute(exists_stmt)).scalar_one_or_none()
    if not exists:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    # 查询当前标准的出入度关系
    stmt = select(StandardRelation).where(
        or_(
            StandardRelation.sourceid == standard_id_str,
            StandardRelation.targetid == standard_id_str,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.delete(
    "/relations/{rel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除关系",
    description="按关系 ID 删除单条关系记录。",
)
async def delete_relation(
    rel_id: int,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(StandardRelation.id).where(StandardRelation.id == rel_id)
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise build_api_error(
            status_code=404,
            code="RELATION_NOT_FOUND",
            message="关系不存在",
            errors=[{"field": "rel_id", "message": "未找到对应关系"}],
            warnings=[],
        )
    relation = await session.get(StandardRelation, rel_id)
    await session.delete(relation)
    await session.commit()
    return None
