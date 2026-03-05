from __future__ import annotations

import uuid
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataStandard, DataStandardCodeLink, StandardCodeItem, StandardCodeList
from app.schemas import CodeItemBase


async def get_code_list_by_id(session: AsyncSession, code_list_id: uuid.UUID) -> StandardCodeList | None:
    stmt = select(StandardCodeList).where(
        StandardCodeList.id == code_list_id,
        StandardCodeList.is_deleted == False,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_bindable_code_list_by_id(session: AsyncSession, code_list_id: uuid.UUID) -> StandardCodeList | None:
    stmt = select(StandardCodeList).where(
        StandardCodeList.id == code_list_id,
        StandardCodeList.is_deleted == False,
        StandardCodeList.status == 1,
        StandardCodeList.is_latest == True,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def exists_code_list_code_version(
    session: AsyncSession,
    *,
    list_code: str,
    version: int,
) -> bool:
    stmt = select(StandardCodeList.id).where(
        StandardCodeList.list_code == list_code,
        StandardCodeList.version == version,
        StandardCodeList.is_deleted == False,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def list_code_lists(
    session: AsyncSession,
    page: int,
    page_size: int,
    list_code: str | None,
    name: str | None,
    status: int | None,
    is_latest: bool | None,
    bindable: bool,
) -> tuple[list[StandardCodeList], int]:
    filters = [StandardCodeList.is_deleted == False]
    if list_code:
        filters.append(StandardCodeList.list_code == list_code)
    if name:
        filters.append(StandardCodeList.name.ilike(f"%{name}%"))
    if status is not None:
        filters.append(StandardCodeList.status == status)
    if is_latest is not None:
        filters.append(StandardCodeList.is_latest == is_latest)
    if bindable:
        filters.extend([StandardCodeList.status == 1, StandardCodeList.is_latest == True])

    count_stmt = select(func.count(StandardCodeList.id)).where(and_(*filters))
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(StandardCodeList)
        .where(and_(*filters))
        .order_by(StandardCodeList.list_code.asc(), StandardCodeList.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def list_code_items(
    session: AsyncSession,
    code_list_id: uuid.UUID,
    page: int,
    page_size: int,
    keyword: str | None,
) -> tuple[list[StandardCodeItem], int]:
    filters = [
        StandardCodeItem.list_id == code_list_id,
        StandardCodeItem.is_deleted == False,
    ]
    if keyword:
        filters.append(
            or_(
                StandardCodeItem.item_code.ilike(f"%{keyword}%"),
                StandardCodeItem.item_name.ilike(f"%{keyword}%"),
                StandardCodeItem.meaning.ilike(f"%{keyword}%"),
            )
        )

    count_stmt = select(func.count(StandardCodeItem.id)).where(and_(*filters))
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(StandardCodeItem)
        .where(and_(*filters))
        .order_by(StandardCodeItem.sort_order.asc(), StandardCodeItem.item_code.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def replace_code_items(
    session: AsyncSession,
    code_list_id: uuid.UUID,
    items: list[CodeItemBase],
) -> None:
    stmt = select(StandardCodeItem).where(
        StandardCodeItem.list_id == code_list_id,
        StandardCodeItem.is_deleted == False,
    )
    result = await session.execute(stmt)
    existing_items = list(result.scalars().all())
    existing_map = {item.item_code: item for item in existing_items}

    incoming_codes = {item.item_code for item in items}
    for item in items:
        existing = existing_map.get(item.item_code)
        if existing:
            existing.item_name = item.item_name
            existing.meaning = item.meaning
            existing.sort_order = item.sort_order
            existing.last_update_user = "api"
        else:
            session.add(
                StandardCodeItem(
                    list_id=code_list_id,
                    item_code=item.item_code,
                    item_name=item.item_name,
                    meaning=item.meaning,
                    sort_order=item.sort_order,
                    is_deleted=False,
                    last_update_user="api",
                )
            )

    for existing in existing_items:
        if existing.item_code not in incoming_codes:
            existing.is_deleted = True
            existing.last_update_user = "api"


async def set_latest_published_code_list(
    session: AsyncSession,
    list_code: str,
    code_list_id: uuid.UUID,
) -> None:
    await session.execute(
        update(StandardCodeList)
        .where(
            StandardCodeList.list_code == list_code,
            StandardCodeList.is_deleted == False,
        )
        .values(is_latest=False)
    )
    await session.execute(
        update(StandardCodeList)
        .where(
            StandardCodeList.list_code == list_code,
            StandardCodeList.id != code_list_id,
            StandardCodeList.status == 1,
            StandardCodeList.is_deleted == False,
        )
        .values(status=2, last_update_user="api")
    )
    await session.execute(
        update(StandardCodeList)
        .where(StandardCodeList.id == code_list_id)
        .values(status=1, is_latest=True, last_update_user="api")
    )


async def create_code_list_revision(
    session: AsyncSession,
    code_list: StandardCodeList,
) -> StandardCodeList:
    max_version_stmt = select(func.max(StandardCodeList.version)).where(
        StandardCodeList.list_code == code_list.list_code,
        StandardCodeList.is_deleted == False,
    )
    max_version = (await session.execute(max_version_stmt)).scalar_one_or_none() or code_list.version

    new_list = StandardCodeList(
        list_code=code_list.list_code,
        name=code_list.name,
        purpose=code_list.purpose,
        status=0,
        version=max_version + 1,
        is_latest=False,
        is_deleted=False,
        last_update_user="api",
    )
    session.add(new_list)
    await session.flush()

    items_stmt = select(StandardCodeItem).where(
        StandardCodeItem.list_id == code_list.id,
        StandardCodeItem.is_deleted == False,
    )
    items = (await session.execute(items_stmt)).scalars().all()
    for item in items:
        session.add(
            StandardCodeItem(
                list_id=new_list.id,
                item_code=item.item_code,
                item_name=item.item_name,
                meaning=item.meaning,
                sort_order=item.sort_order,
                is_deleted=False,
                last_update_user="api",
            )
        )
    return new_list


async def list_code_list_history(
    session: AsyncSession,
    list_code: str,
) -> list[StandardCodeList]:
    stmt = (
        select(StandardCodeList)
        .where(
            StandardCodeList.list_code == list_code,
            StandardCodeList.is_deleted == False,
        )
        .order_by(StandardCodeList.version.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def has_published_standard_bindings(
    session: AsyncSession,
    code_list_id: uuid.UUID,
) -> bool:
    stmt = (
        select(DataStandardCodeLink.id)
        .join(DataStandard, DataStandard.id == DataStandardCodeLink.standard_id)
        .where(
            DataStandardCodeLink.code_list_id == code_list_id,
            DataStandardCodeLink.is_deleted == False,
            DataStandard.is_deleted == False,
            DataStandard.status == 1,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_active_standard_code_link(
    session: AsyncSession,
    standard_id: uuid.UUID,
) -> DataStandardCodeLink | None:
    stmt = select(DataStandardCodeLink).where(
        DataStandardCodeLink.standard_id == standard_id,
        DataStandardCodeLink.is_deleted == False,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_standard_code_link(
    session: AsyncSession,
    standard_id: uuid.UUID,
    code_list_id: uuid.UUID | None,
) -> DataStandardCodeLink | None:
    current_link = await get_active_standard_code_link(session, standard_id)
    if code_list_id is None:
        if current_link:
            current_link.is_deleted = True
            current_link.last_update_user = "api"
        return None

    if current_link:
        current_link.code_list_id = code_list_id
        current_link.last_update_user = "api"
        return current_link

    new_link = DataStandardCodeLink(
        standard_id=standard_id,
        code_list_id=code_list_id,
        is_deleted=False,
        last_update_user="api",
    )
    session.add(new_link)
    await session.flush()
    return new_link


async def get_standard_code_link_detail(
    session: AsyncSession,
    standard_id: uuid.UUID,
) -> tuple[DataStandardCodeLink | None, StandardCodeList | None]:
    stmt = (
        select(DataStandardCodeLink, StandardCodeList)
        .join(StandardCodeList, StandardCodeList.id == DataStandardCodeLink.code_list_id)
        .where(
            DataStandardCodeLink.standard_id == standard_id,
            DataStandardCodeLink.is_deleted == False,
            StandardCodeList.is_deleted == False,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if not row:
        return None, None
    return row[0], row[1]


async def list_code_list_bindings(
    session: AsyncSession,
    code_list_id: uuid.UUID,
    page: int,
    page_size: int,
    published_only: bool,
) -> tuple[list[DataStandard], int]:
    filters = [
        DataStandardCodeLink.code_list_id == code_list_id,
        DataStandardCodeLink.is_deleted == False,
        DataStandard.is_deleted == False,
    ]
    if published_only:
        filters.append(DataStandard.status == 1)

    count_stmt = (
        select(func.count(DataStandard.id))
        .select_from(DataStandardCodeLink)
        .join(DataStandard, DataStandard.id == DataStandardCodeLink.standard_id)
        .where(and_(*filters))
    )
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(DataStandard)
        .select_from(DataStandardCodeLink)
        .join(DataStandard, DataStandard.id == DataStandardCodeLink.standard_id)
        .where(and_(*filters))
        .order_by(DataStandard.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def keyword_search_code_lists(
    session: AsyncSession,
    query: str,
    top_k: int,
    only_bindable: bool,
) -> list[tuple[StandardCodeList, bool, bool]]:
    pattern = f"%{query}%"
    list_match = or_(
        StandardCodeList.list_code.ilike(pattern),
        StandardCodeList.name.ilike(pattern),
        StandardCodeList.purpose.ilike(pattern),
    )
    item_match = exists(
        select(StandardCodeItem.id).where(
            StandardCodeItem.list_id == StandardCodeList.id,
            StandardCodeItem.is_deleted == False,
            or_(
                StandardCodeItem.item_code.ilike(pattern),
                StandardCodeItem.item_name.ilike(pattern),
                StandardCodeItem.meaning.ilike(pattern),
            ),
        )
    )

    filters = [StandardCodeList.is_deleted == False]
    if only_bindable:
        filters.extend([StandardCodeList.status == 1, StandardCodeList.is_latest == True])

    stmt = (
        select(
            StandardCodeList,
            list_match.label("list_match"),
            item_match.label("item_match"),
        )
        .where(and_(*filters))
        .where(or_(list_match, item_match))
        .order_by(StandardCodeList.updated_at.desc())
        .limit(top_k)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [(row[0], bool(row[1]), bool(row[2])) for row in rows]


async def get_standard_code_link_map(
    session: AsyncSession,
    standard_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not standard_ids:
        return set()
    stmt = select(DataStandardCodeLink.standard_id).where(
        DataStandardCodeLink.standard_id.in_(standard_ids),
        DataStandardCodeLink.is_deleted == False,
    )
    result = await session.execute(stmt)
    return {row[0] for row in result.all()}
