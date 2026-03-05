from __future__ import annotations

import uuid
from typing import Sequence
from sqlalchemy import and_, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataStandard, DataStandardCodeLink, StandardI18n
from app.schemas import I18nItem


# 按 ID 获取标准
async def get_standard_by_id(session: AsyncSession, standard_id: uuid.UUID) -> DataStandard | None:
    stmt = select(DataStandard).where(
        DataStandard.id == standard_id,
        DataStandard.is_deleted == False,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# 列表查询 + 分页
async def list_standards(
    session: AsyncSession,
    page: int,
    page_size: int,
    code: str | None,
    name: str | None,
    status: int | None,
    category_id: int | None,
    is_latest: bool | None,
) -> tuple[list[DataStandard], int]:
    filters = [DataStandard.is_deleted == False]
    if code:
        filters.append(DataStandard.code == code)
    if name:
        filters.append(DataStandard.name.ilike(f"%{name}%"))
    if status is not None:
        filters.append(DataStandard.status == status)
    if category_id is not None:
        filters.append(DataStandard.category_id == category_id)
    if is_latest is not None:
        filters.append(DataStandard.is_latest == is_latest)

    count_stmt = select(func.count(DataStandard.id)).where(and_(*filters)) if filters else select(func.count(DataStandard.id))
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(DataStandard)
        .where(and_(*filters))
        .order_by(DataStandard.code, DataStandard.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ) if filters else (
        select(DataStandard)
        .order_by(DataStandard.code, DataStandard.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


# 写入或更新 i18n
async def upsert_i18n(
    session: AsyncSession,
    standard_id: uuid.UUID,
    translations: Sequence[I18nItem],
) -> None:
    for item in translations:
        stmt = select(StandardI18n.id).where(
            StandardI18n.refid == standard_id,
            StandardI18n.fieldname == item.fieldname,
            StandardI18n.language == item.language,
        )
        result = await session.execute(stmt)
        existing_id = result.scalar_one_or_none()
        if existing_id:
            await session.execute(
                update(StandardI18n)
                .where(StandardI18n.id == existing_id)
                .values(content=item.content)
            )
        else:
            session.add(
                StandardI18n(
                    refid=standard_id,
                    fieldname=item.fieldname,
                    language=item.language,
                    content=item.content,
                )
            )


# 读取指定语言的 i18n
async def fetch_i18n(
    session: AsyncSession,
    standard_id: uuid.UUID,
    lang: str,
) -> list[StandardI18n]:
    stmt = select(StandardI18n).where(
        StandardI18n.refid == standard_id,
        StandardI18n.language == lang,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# 将 i18n 内容覆盖到标准对象
async def apply_i18n_overrides(
    standard: DataStandard,
    translations: Sequence[StandardI18n],
) -> None:
    if not translations:
        return
    for item in translations:
        if item.fieldname == "name":
            standard.name = item.content
        elif item.fieldname == "description":
            standard.description = item.content


# 发布时确保同 code 只有一个最新版本
async def set_latest_published(session: AsyncSession, code: str, standard_id: uuid.UUID) -> None:
    await session.execute(
        update(DataStandard)
        .where(
            DataStandard.code == code,
            DataStandard.is_deleted == False,
        )
        .values(is_latest=False)
    )
    await session.execute(
        update(DataStandard)
        .where(
            DataStandard.code == code,
            DataStandard.id != standard_id,
            DataStandard.status == 1,
            DataStandard.is_deleted == False,
        )
        .values(status=2, last_update_user="api")
    )
    await session.execute(
        update(DataStandard)
        .where(DataStandard.id == standard_id)
        .values(status=1, is_latest=True, last_update_user="api")
    )


# 创建新版本（基于现有标准）
async def create_revision(session: AsyncSession, standard: DataStandard) -> DataStandard:
    max_version_stmt = select(func.max(DataStandard.version)).where(
        DataStandard.code == standard.code,
        DataStandard.is_deleted == False,
    )
    max_version = (await session.execute(max_version_stmt)).scalar_one_or_none() or standard.version

    new_standard = DataStandard(
        code=standard.code,
        name=standard.name,
        description=standard.description,
        status=0,
        version=max_version + 1,
        is_latest=False,
        is_deleted=False,
        category_id=standard.category_id,
        extattributes=standard.extattributes,
        last_update_user="api",
    )
    session.add(new_standard)
    return new_standard


async def exists_standard_code_version(
    session: AsyncSession,
    *,
    code: str,
    version: int,
) -> bool:
    stmt = select(DataStandard.id).where(
        DataStandard.code == code,
        DataStandard.version == version,
        DataStandard.is_deleted == False,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def list_standards_readonly(
    session: AsyncSession,
    page: int,
    page_size: int,
    keyword: str | None,
    status: int | None,
    is_latest: bool | None,
    order_by: str,
    order_dir: str,
) -> tuple[list[tuple[DataStandard, bool]], int]:
    filters = [DataStandard.is_deleted == False]
    if keyword:
        filters.append(
            DataStandard.code.ilike(f"%{keyword}%")
            | DataStandard.name.ilike(f"%{keyword}%")
            | DataStandard.description.ilike(f"%{keyword}%")
        )
    if status is not None:
        filters.append(DataStandard.status == status)
    if is_latest is not None:
        filters.append(DataStandard.is_latest == is_latest)

    count_stmt = select(func.count(DataStandard.id)).where(and_(*filters))
    total = (await session.execute(count_stmt)).scalar_one()

    has_code_list_expr = exists(
        select(DataStandardCodeLink.id).where(
            DataStandardCodeLink.standard_id == DataStandard.id,
            DataStandardCodeLink.is_deleted == False,
        )
    )
    order_fields = {
        "updated_at": DataStandard.updated_at,
        "created_at": DataStandard.created_at,
        "code": DataStandard.code,
        "name": DataStandard.name,
        "version": DataStandard.version,
    }
    order_column = order_fields.get(order_by, DataStandard.updated_at)
    order_expr = order_column.asc() if order_dir == "asc" else order_column.desc()
    stmt = (
        select(DataStandard, has_code_list_expr.label("has_code_list"))
        .where(and_(*filters))
        .order_by(order_expr, DataStandard.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).all()
    return [(row[0], bool(row[1])) for row in rows], total


async def count_standards_readonly_status(
    session: AsyncSession,
    keyword: str | None,
    is_latest: bool | None,
) -> dict[int, int]:
    filters = [DataStandard.is_deleted == False]
    if keyword:
        filters.append(
            DataStandard.code.ilike(f"%{keyword}%")
            | DataStandard.name.ilike(f"%{keyword}%")
            | DataStandard.description.ilike(f"%{keyword}%")
        )
    if is_latest is not None:
        filters.append(DataStandard.is_latest == is_latest)

    stmt = (
        select(DataStandard.status, func.count(DataStandard.id))
        .where(and_(*filters))
        .group_by(DataStandard.status)
    )
    rows = (await session.execute(stmt)).all()
    return {int(status): int(count) for status, count in rows}
