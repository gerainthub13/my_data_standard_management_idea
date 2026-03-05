import uuid
from typing import Literal
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import build_api_error
from app.models import Category, DataStandard
from app.schemas import (
    CodeListSummary,
    StandardCodeBindingOut,
    StandardCodeBindingUpdate,
    StandardCreate,
    StandardDetailOut,
    StandardReadonlyListOut,
    StandardReadonlyStatusStatsOut,
    StandardReadonlyStatusCount,
    StandardListOut,
    StandardOut,
    StandardReadonlyItem,
    StandardStatusUpdate,
    StandardUpdate,
)
from app.services.embedding import schedule_embedding_rebuild
from app.services.standards import (
    apply_i18n_overrides,
    create_revision,
    exists_standard_code_version,
    fetch_i18n,
    get_standard_by_id,
    count_standards_readonly_status,
    list_standards,
    list_standards_readonly,
    set_latest_published,
    upsert_i18n,
)
from app.services.code_lists import (
    get_bindable_code_list_by_id,
    get_standard_code_link_map,
    get_standard_code_link_detail,
    set_standard_code_link,
)
from app.validators import normalize_language


# 标准管理 API
router = APIRouter(prefix="/api/v1/standards", tags=["standards"])
settings = get_settings()


async def _ensure_active_category_exists(session: AsyncSession, category_id: int | None) -> None:
    if category_id is None:
        return
    stmt = select(Category.id).where(
        Category.id == category_id,
        Category.is_deleted == False,
    )
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise build_api_error(
            status_code=400,
            code="CATEGORY_NOT_FOUND",
            message="category_id 对应分类不存在或已删除",
            errors=[{"field": "category_id", "message": "分类不存在"}],
            warnings=["请先创建分类，或传入有效的 category_id。"],
        )


def _resolve_request_language(lang: str | None, accept_language: str | None) -> str:
    if lang:
        try:
            return normalize_language(lang)
        except ValueError as exc:
            raise build_api_error(
                status_code=400,
                code="LANGUAGE_INVALID",
                message="lang 参数不合法",
                errors=[{"field": "lang", "message": str(exc)}],
                warnings=["示例：zh、en、ja。"],
            )
    if accept_language:
        # Accept-Language 可能为 "en-US,en;q=0.9"
        token = accept_language.split(",")[0].split(";")[0].strip()
        if token:
            try:
                return normalize_language(token.split("-")[0])
            except ValueError:
                pass
    return settings.default_language


@router.post(
    "",
    response_model=StandardOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建数据标准",
    description="创建草稿标准，执行名称非法字符校验、分类存在性校验、code+version 唯一性校验，并触发向量重建任务。",
)
async def create_standard(
    payload: StandardCreate,
    session: AsyncSession = Depends(get_session),
):
    await _ensure_active_category_exists(session, payload.category_id)
    if await exists_standard_code_version(session, code=payload.code, version=1):
        raise build_api_error(
            status_code=409,
            code="STANDARD_CODE_VERSION_CONFLICT",
            message="标准编码与版本组合已存在",
            errors=[{"field": "code", "message": "code=当前值 的 version=1 已存在"}],
            warnings=["请使用 revision 接口创建新版本。"],
        )

    standard = DataStandard(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        category_id=payload.category_id,
        extattributes=payload.extattributes,
        status=0,
        version=1,
        is_latest=False,
        is_deleted=False,
        last_update_user="api",
    )
    session.add(standard)
    try:
        await session.flush()
        if payload.translations:
            await upsert_i18n(session, standard.id, payload.translations)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="STANDARD_CREATE_CONFLICT",
            message="标准创建失败：关键字段组合冲突",
            errors=[{"field": "code/version", "message": "生效数据中 code+version 必须唯一"}],
            warnings=["请检查是否存在并发创建相同编码标准。"],
        )

    await session.refresh(standard)

    # 异步触发 embedding 重建
    schedule_embedding_rebuild(str(standard.id), settings.default_language)
    return standard


@router.get(
    "",
    response_model=StandardListOut,
    summary="分页查询数据标准",
    description="支持 code/name/status/category_id/is_latest 过滤，默认仅返回未删除数据。",
)
async def get_standards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    code: str | None = None,
    name: str | None = None,
    status: int | None = Query(default=None, ge=0, le=4),
    category_id: int | None = None,
    is_latest: bool | None = None,
    session: AsyncSession = Depends(get_session),
):
    # 列表查询
    items, total = await list_standards(session, page, page_size, code, name, status, category_id, is_latest)
    return StandardListOut(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/readonly/list",
    response_model=StandardReadonlyListOut,
    summary="只读标准清单",
    description="支持关键词、状态、is_latest 和排序筛选，包含是否绑定标准代码标记。",
)
async def get_standards_readonly(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    keyword: str | None = Query(default=None),
    status: int | None = Query(default=None, ge=0, le=4),
    is_latest: bool | None = Query(default=None),
    order_by: Literal["updated_at", "created_at", "code", "name", "version"] = Query(default="updated_at"),
    order_dir: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_session),
):
    rows, total = await list_standards_readonly(
        session=session,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        is_latest=is_latest,
        order_by=order_by,
        order_dir=order_dir,
    )
    items = []
    for standard, has_code_list in rows:
        payload = StandardOut.model_validate(standard).model_dump()
        payload["has_code_list"] = has_code_list
        items.append(StandardReadonlyItem(**payload))
    return StandardReadonlyListOut(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/readonly/stats",
    response_model=StandardReadonlyStatusStatsOut,
    summary="只读标准状态统计",
    description="按关键词与 is_latest 条件统计标准状态数量，用于只读界面状态面板。",
)
async def get_standards_readonly_stats(
    keyword: str | None = Query(default=None),
    is_latest: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    counts_map = await count_standards_readonly_status(
        session=session,
        keyword=keyword,
        is_latest=is_latest,
    )
    counts = StandardReadonlyStatusCount(
        draft=counts_map.get(0, 0),
        published=counts_map.get(1, 0),
        retired=counts_map.get(2, 0),
        deprecated=counts_map.get(3, 0),
        other=counts_map.get(4, 0),
    )
    total = counts.draft + counts.published + counts.retired + counts.deprecated + counts.other
    return StandardReadonlyStatusStatsOut(total=total, counts=counts)


@router.get(
    "/{standard_id}",
    response_model=StandardDetailOut,
    summary="查询标准详情",
    description="根据标准 ID 查询详情，并按 lang 或 Accept-Language 返回对应语言内容；无匹配语言时自动回退默认语言。",
)
async def get_standard_detail(
    standard_id: uuid.UUID,
    lang: str | None = None,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    session: AsyncSession = Depends(get_session),
):
    # 详情查询（含 i18n）
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    resolved_lang = _resolve_request_language(lang, accept_language)
    translations = await fetch_i18n(session, standard.id, resolved_lang)
    if not translations and resolved_lang != settings.default_language:
        translations = await fetch_i18n(session, standard.id, settings.default_language)

    _, code_list = await get_standard_code_link_detail(session, standard.id)
    await apply_i18n_overrides(standard, translations)
    return StandardDetailOut(
        **StandardOut.model_validate(standard).model_dump(),
        translations=[
            {"fieldname": t.fieldname, "language": t.language, "content": t.content}
            for t in translations
        ]
        if translations
        else None,
        code_list=CodeListSummary.model_validate(code_list) if code_list else None,
    )


@router.put(
    "/{standard_id}",
    response_model=StandardOut,
    summary="更新数据标准",
    description="仅允许草稿和退役版本更新，支持同步更新 i18n，并触发向量重建。",
)
async def update_standard(
    standard_id: uuid.UUID,
    payload: StandardUpdate,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )
    if standard.status not in (0, 2):
        raise build_api_error(
            status_code=400,
            code="STANDARD_STATUS_INVALID",
            message="仅允许草稿或退役状态的标准被更新",
            errors=[{"field": "status", "message": "当前状态不允许更新"}],
            warnings=["已发布版本请先创建 revision，再编辑新版本。"],
        )

    if payload.category_id is not None:
        await _ensure_active_category_exists(session, payload.category_id)

    updates = payload.model_dump(exclude_unset=True, exclude={"translations"})
    for key, value in updates.items():
        setattr(standard, key, value)
    standard.last_update_user = "api"

    if payload.translations is not None:
        await upsert_i18n(session, standard.id, payload.translations)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="STANDARD_UPDATE_CONFLICT",
            message="标准更新失败：数据约束冲突",
            errors=[{"field": "payload", "message": "请检查字段值与唯一约束"}],
            warnings=[],
        )

    await session.refresh(standard)

    schedule_embedding_rebuild(str(standard.id), settings.default_language)
    return standard


@router.delete(
    "/{standard_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除数据标准（软删除）",
    description="按软删除处理，不物理删除，删除后 status=3 且 is_latest=false。",
)
async def delete_standard(
    standard_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    # 按 PRD 执行软删除，避免物理删除影响历史追溯。
    standard.is_deleted = True
    standard.status = 3
    standard.is_latest = False
    standard.last_update_user = "api"
    await session.commit()
    return None


@router.post(
    "/{standard_id}/revision",
    response_model=StandardOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建标准新版本",
    description="基于现有标准复制生成新版本（version 自动按同 code 最大版本 +1）。",
)
async def create_standard_revision(
    standard_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )
    if standard.status == 3:
        raise build_api_error(
            status_code=400,
            code="STANDARD_DELETED",
            message="已删除标准不允许创建新版本",
            errors=[{"field": "standard_id", "message": "该标准已删除"}],
            warnings=[],
        )

    new_standard = await create_revision(session, standard)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="STANDARD_REVISION_CONFLICT",
            message="新版本创建失败：版本号冲突",
            errors=[{"field": "code/version", "message": "存在并发生成相同版本"}],
            warnings=["请重试 revision 接口。"],
        )

    await session.refresh(new_standard)
    return new_standard


@router.patch(
    "/{standard_id}/publish",
    response_model=StandardOut,
    summary="发布标准版本",
    description="发布指定版本，并确保同 code 下仅一个 is_latest=true 且 status=1。",
)
async def publish_standard(
    standard_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )
    if standard.status == 3:
        raise build_api_error(
            status_code=400,
            code="STANDARD_DELETED",
            message="已删除标准不允许发布",
            errors=[{"field": "status", "message": "已删除标准不可发布"}],
            warnings=[],
        )

    await set_latest_published(session, standard.code, standard.id)
    standard.last_update_user = "api"
    await session.commit()
    await session.refresh(standard)
    return standard


@router.patch(
    "/{standard_id}/status",
    response_model=StandardOut,
    summary="更新标准状态",
    description="更新标准状态；当状态为 published 时自动执行发布一致性逻辑。",
)
async def update_standard_status(
    standard_id: uuid.UUID,
    payload: StandardStatusUpdate,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    if int(payload.status) == 1:
        await set_latest_published(session, standard.code, standard.id)
    else:
        standard.status = int(payload.status)
        standard.is_latest = False
    standard.last_update_user = "api"

    await session.commit()
    await session.refresh(standard)
    return standard


@router.get(
    "/{standard_id}/code-list",
    response_model=StandardCodeBindingOut,
    summary="查询标准绑定码表",
    description="返回指定标准当前绑定的码表摘要；未绑定时 code_list_id 和 code_list 为 null。",
)
async def get_standard_code_list_binding(
    standard_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    link, code_list = await get_standard_code_link_detail(session, standard.id)
    if not link or not code_list:
        return StandardCodeBindingOut(
            standard_id=standard.id,
            code_list_id=None,
            code_list=None,
        )
    return StandardCodeBindingOut(
        standard_id=standard.id,
        code_list_id=link.code_list_id,
        code_list=CodeListSummary.model_validate(code_list),
    )


@router.put(
    "/{standard_id}/code-list",
    response_model=StandardCodeBindingOut,
    summary="绑定或解绑标准码表",
    description="设置标准绑定码表；code_list_id=null 表示解绑。仅允许绑定已发布且最新版本码表。",
)
async def put_standard_code_list_binding(
    standard_id: uuid.UUID,
    payload: StandardCodeBindingUpdate,
    session: AsyncSession = Depends(get_session),
):
    standard = await get_standard_by_id(session, standard_id)
    if not standard:
        raise build_api_error(
            status_code=404,
            code="STANDARD_NOT_FOUND",
            message="数据标准不存在或已删除",
            errors=[{"field": "standard_id", "message": "未找到对应标准"}],
            warnings=[],
        )

    if payload.code_list_id is not None:
        bindable = await get_bindable_code_list_by_id(session, payload.code_list_id)
        if not bindable:
            raise build_api_error(
                status_code=400,
                code="CODE_LIST_BIND_INVALID",
                message="仅允许绑定已发布且最新的码表版本",
                errors=[{"field": "code_list_id", "message": "码表不存在、已删除或非可绑定版本"}],
                warnings=["请先发布码表最新版本后再绑定。"],
            )

    try:
        await set_standard_code_link(session, standard.id, payload.code_list_id)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="STANDARD_CODE_LINK_CONFLICT",
            message="标准绑定码表失败：数据约束冲突",
            errors=[{"field": "standard_id", "message": "当前标准绑定记录冲突，请重试"}],
            warnings=[],
        )

    link, code_list = await get_standard_code_link_detail(session, standard.id)
    if not link or not code_list:
        return StandardCodeBindingOut(
            standard_id=standard.id,
            code_list_id=None,
            code_list=None,
        )
    return StandardCodeBindingOut(
        standard_id=standard.id,
        code_list_id=link.code_list_id,
        code_list=CodeListSummary.model_validate(code_list),
    )


@router.get(
    "/{code}/history",
    response_model=list[StandardOut],
    summary="查询标准历史版本",
    description="按 code 查询全部未删除历史版本，按 version 倒序返回。",
)
async def standard_history(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    # 版本历史
    stmt = (
        select(DataStandard)
        .where(
            DataStandard.code == code,
            DataStandard.is_deleted == False,
        )
        .order_by(DataStandard.version.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
