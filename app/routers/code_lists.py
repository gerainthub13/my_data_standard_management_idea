import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import build_api_error
from app.models import DataStandardCodeLink, StandardCodeItem, StandardCodeList
from app.schemas import (
    CodeListBindingListOut,
    CodeListCreate,
    CodeListDetailOut,
    CodeListItemListOut,
    CodeListItemsReplaceRequest,
    CodeListKeywordSearchRequest,
    CodeListKeywordSearchResponse,
    CodeListListOut,
    CodeListOut,
    CodeListStatusUpdate,
    CodeListUpdate,
)
from app.services.code_lists import (
    create_code_list_revision,
    exists_code_list_code_version,
    get_code_list_by_id,
    has_published_standard_bindings,
    keyword_search_code_lists,
    list_code_items,
    list_code_list_bindings,
    list_code_list_history,
    list_code_lists,
    replace_code_items,
    set_latest_published_code_list,
)


router = APIRouter(prefix="/api/v1/code-lists", tags=["code-lists"])


def _ensure_code_list_editable(code_list: StandardCodeList) -> None:
    if code_list.status != 0:
        raise build_api_error(
            status_code=400,
            code="CODE_LIST_STATUS_INVALID",
            message="仅允许草稿状态的码表被更新",
            errors=[{"field": "status", "message": "当前状态不允许编辑"}],
            warnings=["已发布版本请先创建 revision，再编辑新版本。"],
        )


@router.post(
    "",
    response_model=CodeListOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建标准代码列表",
    description="创建草稿码表，默认 version=1/status=0，支持同时提交子项。",
)
async def create_code_list(
    payload: CodeListCreate,
    session: AsyncSession = Depends(get_session),
):
    if await exists_code_list_code_version(session, list_code=payload.list_code, version=1):
        raise build_api_error(
            status_code=409,
            code="CODE_LIST_CODE_VERSION_CONFLICT",
            message="码表编码与版本组合已存在",
            errors=[{"field": "list_code", "message": "list_code=当前值 的 version=1 已存在"}],
            warnings=["请使用 revision 接口创建新版本。"],
        )

    code_list = StandardCodeList(
        list_code=payload.list_code,
        name=payload.name,
        purpose=payload.purpose,
        status=0,
        version=1,
        is_latest=False,
        is_deleted=False,
        last_update_user="api",
    )
    session.add(code_list)

    try:
        await session.flush()
        if payload.items:
            await replace_code_items(session, code_list.id, payload.items)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="CODE_LIST_CREATE_CONFLICT",
            message="码表创建失败：关键字段组合冲突",
            errors=[{"field": "list_code/version", "message": "生效数据中 list_code+version 必须唯一"}],
            warnings=[],
        )

    await session.refresh(code_list)
    return code_list


@router.post(
    "/search",
    response_model=CodeListKeywordSearchResponse,
    summary="关键词搜索标准代码",
    description="按关键词检索码表主表和子项内容；支持 only_bindable=true 仅返回可绑定版本。",
)
async def search_code_lists(
    payload: CodeListKeywordSearchRequest,
    session: AsyncSession = Depends(get_session),
):
    rows = await keyword_search_code_lists(
        session=session,
        query=payload.query,
        top_k=payload.top_k,
        only_bindable=payload.only_bindable,
    )
    items = []
    for code_list, list_matched, item_matched in rows:
        matched_by: list[str] = []
        if list_matched:
            matched_by.append("list")
        if item_matched:
            matched_by.append("item")
        items.append(
            {
                "id": code_list.id,
                "list_code": code_list.list_code,
                "name": code_list.name,
                "purpose": code_list.purpose,
                "version": code_list.version,
                "status": code_list.status,
                "is_latest": code_list.is_latest,
                "matched_by": matched_by,
            }
        )
    return CodeListKeywordSearchResponse(items=items)


@router.get(
    "",
    response_model=CodeListListOut,
    summary="分页查询码表",
    description="支持 list_code/name/status/is_latest 过滤；可通过 bindable=true 仅查询可绑定版本。",
)
async def get_code_lists(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    list_code: str | None = None,
    name: str | None = None,
    status: int | None = Query(default=None, ge=0, le=4),
    is_latest: bool | None = None,
    bindable: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    items, total = await list_code_lists(
        session=session,
        page=page,
        page_size=page_size,
        list_code=list_code,
        name=name,
        status=status,
        is_latest=is_latest,
        bindable=bindable,
    )
    return CodeListListOut(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/code/{list_code}/history",
    response_model=list[CodeListOut],
    summary="查询码表历史版本",
    description="按 list_code 查询全部未删除历史版本，按 version 倒序返回。",
)
async def code_list_history(
    list_code: str,
    session: AsyncSession = Depends(get_session),
):
    return await list_code_list_history(session, list_code)


@router.get(
    "/{code_list_id}/bindings",
    response_model=CodeListBindingListOut,
    summary="查询码表引用标准",
    description="分页返回当前码表被哪些标准引用；可选仅查看已发布标准。",
)
async def get_code_list_bindings(
    code_list_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    published_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )

    items, total = await list_code_list_bindings(
        session=session,
        code_list_id=code_list_id,
        page=page,
        page_size=page_size,
        published_only=published_only,
    )
    return CodeListBindingListOut(
        items=[item for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{code_list_id}",
    response_model=CodeListDetailOut,
    summary="查询码表详情",
    description="按码表 ID 查询详情，支持 include_items 控制是否返回子项。",
)
async def get_code_list_detail(
    code_list_id: uuid.UUID,
    include_items: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )

    items = None
    if include_items:
        stmt = (
            select(StandardCodeItem)
            .where(
                StandardCodeItem.list_id == code_list.id,
                StandardCodeItem.is_deleted == False,
            )
            .order_by(StandardCodeItem.sort_order.asc(), StandardCodeItem.item_code.asc())
        )
        items = list((await session.execute(stmt)).scalars().all())

    return CodeListDetailOut(
        **CodeListOut.model_validate(code_list).model_dump(),
        items=[item for item in items] if items is not None else None,
    )


@router.put(
    "/{code_list_id}",
    response_model=CodeListOut,
    summary="更新码表主表",
    description="仅允许草稿状态更新。",
)
async def update_code_list(
    code_list_id: uuid.UUID,
    payload: CodeListUpdate,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )
    _ensure_code_list_editable(code_list)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(code_list, key, value)
    code_list.last_update_user = "api"

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="CODE_LIST_UPDATE_CONFLICT",
            message="码表更新失败：数据约束冲突",
            errors=[{"field": "payload", "message": "请检查字段值与唯一约束"}],
            warnings=[],
        )

    await session.refresh(code_list)
    return code_list


@router.delete(
    "/{code_list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除码表（软删除）",
    description="按软删除处理；若存在已发布标准绑定则拒绝删除。",
)
async def delete_code_list(
    code_list_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )

    if await has_published_standard_bindings(session, code_list.id):
        raise build_api_error(
            status_code=409,
            code="CODE_LIST_IN_USE",
            message="当前码表已被已发布标准引用，不能删除",
            errors=[{"field": "code_list_id", "message": "请先解除引用或变更标准版本"}],
            warnings=[],
        )

    code_list.is_deleted = True
    code_list.status = 3
    code_list.is_latest = False
    code_list.last_update_user = "api"

    await session.execute(
        update(StandardCodeItem)
        .where(
            StandardCodeItem.list_id == code_list.id,
            StandardCodeItem.is_deleted == False,
        )
        .values(is_deleted=True, last_update_user="api")
    )
    await session.execute(
        update(DataStandardCodeLink)
        .where(
            DataStandardCodeLink.code_list_id == code_list.id,
            DataStandardCodeLink.is_deleted == False,
        )
        .values(is_deleted=True, last_update_user="api")
    )
    await session.commit()
    return None


@router.post(
    "/{code_list_id}/revision",
    response_model=CodeListOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建码表新版本",
    description="基于现有码表复制生成新版本（version 自动按同 list_code 最大版本 +1，复制全部生效子项）。",
)
async def create_revision(
    code_list_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )
    if code_list.status == 3:
        raise build_api_error(
            status_code=400,
            code="CODE_LIST_DELETED",
            message="已删除码表不允许创建新版本",
            errors=[{"field": "code_list_id", "message": "该码表已删除"}],
            warnings=[],
        )

    new_list = await create_code_list_revision(session, code_list)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="CODE_LIST_REVISION_CONFLICT",
            message="新版本创建失败：版本号冲突",
            errors=[{"field": "list_code/version", "message": "存在并发生成相同版本"}],
            warnings=["请重试 revision 接口。"],
        )

    await session.refresh(new_list)
    return new_list


@router.patch(
    "/{code_list_id}/publish",
    response_model=CodeListOut,
    summary="发布码表版本",
    description="发布指定版本，并确保同 list_code 下仅一个 is_latest=true 且 status=1。",
)
async def publish_code_list(
    code_list_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )
    if code_list.status == 3:
        raise build_api_error(
            status_code=400,
            code="CODE_LIST_DELETED",
            message="已删除码表不允许发布",
            errors=[{"field": "status", "message": "已删除码表不可发布"}],
            warnings=[],
        )

    await set_latest_published_code_list(session, code_list.list_code, code_list.id)
    code_list.last_update_user = "api"
    await session.commit()
    await session.refresh(code_list)
    return code_list


@router.patch(
    "/{code_list_id}/status",
    response_model=CodeListOut,
    summary="更新码表状态",
    description="更新码表状态；当状态为 published 时自动执行发布一致性逻辑。",
)
async def update_code_list_status(
    code_list_id: uuid.UUID,
    payload: CodeListStatusUpdate,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )

    if int(payload.status) == 1:
        await set_latest_published_code_list(session, code_list.list_code, code_list.id)
    else:
        code_list.status = int(payload.status)
        code_list.is_latest = False
    code_list.last_update_user = "api"

    await session.commit()
    await session.refresh(code_list)
    return code_list


@router.get(
    "/{code_list_id}/items",
    response_model=CodeListItemListOut,
    summary="分页查询码表子项",
    description="支持 item_code/item_name/meaning 关键词过滤。",
)
async def get_code_list_items(
    code_list_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )

    items, total = await list_code_items(session, code_list_id, page, page_size, keyword)
    return CodeListItemListOut(items=items, total=total, page=page, page_size=page_size)


@router.put(
    "/{code_list_id}/items",
    response_model=CodeListItemListOut,
    summary="批量替换码表子项",
    description="覆盖式写入子项：仅草稿状态可编辑；未提交的旧子项将被逻辑删除。",
)
async def put_code_list_items(
    code_list_id: uuid.UUID,
    payload: CodeListItemsReplaceRequest,
    session: AsyncSession = Depends(get_session),
):
    code_list = await get_code_list_by_id(session, code_list_id)
    if not code_list:
        raise build_api_error(
            status_code=404,
            code="CODE_LIST_NOT_FOUND",
            message="码表不存在或已删除",
            errors=[{"field": "code_list_id", "message": "未找到对应码表"}],
            warnings=[],
        )
    _ensure_code_list_editable(code_list)

    try:
        await replace_code_items(session, code_list_id, payload.items)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="CODE_ITEM_UPSERT_CONFLICT",
            message="子项更新失败：item_code 唯一约束冲突",
            errors=[{"field": "items", "message": "同码表下 item_code 不可重复"}],
            warnings=[],
        )

    items, total = await list_code_items(session, code_list_id, page=1, page_size=500, keyword=None)
    return CodeListItemListOut(items=items, total=total, page=1, page_size=500)
