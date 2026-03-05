from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import build_api_error
from app.models import Category
from app.schemas import CategoryCreate, CategoryListOut, CategoryOut, CategoryUpdate


# 分类管理 API
router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


async def _get_active_category_by_id(session: AsyncSession, category_id: int) -> Category | None:
    stmt = select(Category).where(
        Category.id == category_id,
        Category.is_deleted == False,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _ensure_category_name_unique(
    session: AsyncSession,
    *,
    name: str,
    parent_id: int | None,
    exclude_id: int | None = None,
) -> None:
    filters = [
        Category.name == name,
        Category.is_deleted == False,
    ]
    if parent_id is None:
        filters.append(Category.parent_id.is_(None))
    else:
        filters.append(Category.parent_id == parent_id)

    if exclude_id is not None:
        filters.append(Category.id != exclude_id)

    stmt = select(Category.id).where(and_(*filters))
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise build_api_error(
            status_code=409,
            code="CATEGORY_NAME_CONFLICT",
            message="同一父分类下的分类名称已存在，请使用其他名称",
            errors=[{"field": "name", "message": "同父节点下，生效分类名称必须唯一"}],
            warnings=["不同父分类下允许同名分类。"],
        )


async def _ensure_parent_category_valid(
    session: AsyncSession,
    *,
    parent_id: int,
    current_id: int | None = None,
) -> None:
    parent = await _get_active_category_by_id(session, parent_id)
    if not parent:
        raise build_api_error(
            status_code=400,
            code="CATEGORY_PARENT_NOT_FOUND",
            message="parent_id 对应的父分类不存在或已删除",
            errors=[{"field": "parent_id", "message": "父分类不存在"}],
            warnings=["请先创建父分类后再重试。"],
        )

    # 防止更新时将节点挂到自己或自己的后代下，导致树结构出现环。
    if current_id is not None:
        if parent_id == current_id:
            raise build_api_error(
                status_code=400,
                code="CATEGORY_PARENT_INVALID",
                message="parent_id 不能等于当前分类 ID",
                errors=[{"field": "parent_id", "message": "父分类不能为自身"}],
                warnings=[],
            )

        cursor = parent.parent_id
        visited: set[int] = {parent_id}
        while cursor is not None:
            if cursor == current_id:
                raise build_api_error(
                    status_code=400,
                    code="CATEGORY_PARENT_LOOP",
                    message="不允许把分类更新为其子孙节点的子节点",
                    errors=[{"field": "parent_id", "message": "分类层级存在环"}],
                    warnings=["请调整 parent_id，保持树结构无环。"],
                )
            if cursor in visited:
                break
            visited.add(cursor)
            stmt = select(Category.parent_id).where(
                Category.id == cursor,
                Category.is_deleted == False,
            )
            cursor = (await session.execute(stmt)).scalar_one_or_none()


@router.get(
    "",
    response_model=CategoryListOut,
    summary="查询分类",
    description="支持按 ID 精确查询，也支持关键词分页查询；可通过 allow_empty_keyword=true 允许无关键词分页浏览。",
)
async def list_categories(
    category_id: int | None = Query(default=None, alias="id", ge=1),
    keyword: str | None = Query(default=None, description="分类名称关键词（未传 id 时必填）"),
    allow_empty_keyword: bool = Query(default=False, description="是否允许 keyword 为空并返回分页列表"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    parent_id: int | None = Query(default=None, ge=1),
    scope: Literal["standard", "metric", "bizdict"] | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    # 按 ID 查询（详情）
    if category_id is not None:
        category = await _get_active_category_by_id(session, category_id)
        if not category:
            raise build_api_error(
                status_code=404,
                code="CATEGORY_NOT_FOUND",
                message="分类不存在或已删除",
                errors=[{"field": "id", "message": "未找到对应分类"}],
                warnings=[],
            )
        return CategoryListOut(items=[category], total=1, page=1, page_size=1)

    # 按配置约束：未传 ID 时，默认要求提供关键词；可用 allow_empty_keyword 放开。
    normalized_keyword = (keyword or "").strip()
    if not normalized_keyword and not allow_empty_keyword:
        raise build_api_error(
            status_code=400,
            code="CATEGORY_QUERY_INVALID",
            message="未提供 ID 时必须提供 keyword，或显式传 allow_empty_keyword=true",
            errors=[{"field": "keyword", "message": "keyword 不能为空"}],
            warnings=["可改为传 id 进行单条查询，或开启 allow_empty_keyword。"],
        )

    filters = [Category.is_deleted == False]
    if normalized_keyword:
        filters.append(Category.name.ilike(f"%{normalized_keyword}%"))

    if parent_id is not None:
        filters.append(Category.parent_id == parent_id)
    if scope:
        filters.append(Category.scope == scope)

    count_stmt = select(func.count(Category.id)).where(and_(*filters))
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(Category)
        .where(and_(*filters))
        .order_by(Category.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    return CategoryListOut(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建分类",
    description="创建前会执行名称非法字符校验、父分类存在性校验、名称唯一校验。",
)
async def create_category(
    payload: CategoryCreate,
    session: AsyncSession = Depends(get_session),
):
    if payload.parent_id is not None:
        await _ensure_parent_category_valid(session, parent_id=payload.parent_id)
    await _ensure_category_name_unique(session, name=payload.name, parent_id=payload.parent_id)

    category = Category(
        **payload.model_dump(),
        is_deleted=False,
        last_update_user="api",
    )
    session.add(category)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="CATEGORY_CREATE_CONFLICT",
            message="分类创建失败：同父分类名称重复或约束冲突",
            errors=[{"field": "name,parent_id", "message": "请确认同父节点下名称唯一"}],
            warnings=["如并发创建同名分类，请重试并更换名称或父节点。"],
        )

    await session.refresh(category)
    return category


@router.put(
    "/{category_id}",
    response_model=CategoryOut,
    summary="更新分类",
    description="更新前会验证分类存在性、父分类合法性及名称唯一性。",
)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: AsyncSession = Depends(get_session),
):
    category = await _get_active_category_by_id(session, category_id)
    if not category:
        raise build_api_error(
            status_code=404,
            code="CATEGORY_NOT_FOUND",
            message="分类不存在或已删除",
            errors=[{"field": "category_id", "message": "未找到对应分类"}],
            warnings=[],
        )
    if category.category_type == "system":
        raise build_api_error(
            status_code=403,
            code="CATEGORY_SYSTEM_LOCKED",
            message="系统预置分类不允许通过 API 修改",
            errors=[{"field": "category_type", "message": "system 分类不可修改"}],
            warnings=["如需调整系统分类，请使用数据库初始化脚本或管理后台。"],
        )

    updates = payload.model_dump(exclude_unset=True)
    next_name = updates.get("name")
    if next_name is None:
        next_name = category.name
    next_parent_id = updates.get("parent_id", category.parent_id)
    if ("name" in updates and updates["name"] is not None) or "parent_id" in updates:
        await _ensure_category_name_unique(
            session,
            name=next_name,
            parent_id=next_parent_id,
            exclude_id=category_id,
        )

    if "parent_id" in updates and updates["parent_id"] is not None:
        await _ensure_parent_category_valid(session, parent_id=updates["parent_id"], current_id=category_id)

    for key, value in updates.items():
        setattr(category, key, value)
    category.last_update_user = "api"
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise build_api_error(
            status_code=409,
            code="CATEGORY_UPDATE_CONFLICT",
            message="分类更新失败：数据约束冲突",
            errors=[{"field": "name,parent_id", "message": "同父节点下分类名称可能与现有数据重复"}],
            warnings=["请检查 parent_id 与 name 后重试。"],
        )

    await session.refresh(category)
    return category


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除分类（软删除）",
    description="仅支持软删除；若存在子分类会拒绝删除；system 分类不允许删除。",
)
async def delete_category(
    category_id: int,
    session: AsyncSession = Depends(get_session),
):
    category = await _get_active_category_by_id(session, category_id)
    if not category:
        raise build_api_error(
            status_code=404,
            code="CATEGORY_NOT_FOUND",
            message="分类不存在或已删除",
            errors=[{"field": "category_id", "message": "未找到对应分类"}],
            warnings=[],
        )
    if category.category_type == "system":
        raise build_api_error(
            status_code=403,
            code="CATEGORY_SYSTEM_LOCKED",
            message="系统预置分类不允许通过 API 删除",
            errors=[{"field": "category_type", "message": "system 分类不可删除"}],
            warnings=["请保留系统分类用于基础能力支撑。"],
        )

    child_stmt = select(func.count(Category.id)).where(
        Category.parent_id == category_id,
        Category.is_deleted == False,
    )
    child_count = (await session.execute(child_stmt)).scalar_one()
    if child_count > 0:
        raise build_api_error(
            status_code=409,
            code="CATEGORY_HAS_CHILDREN",
            message="当前分类下存在子分类，不能删除",
            errors=[{"field": "category_id", "message": "请先处理子分类"}],
            warnings=["若需要级联删除，请在后续版本中启用该策略。"],
        )

    # 按 PRD 要求执行软删除，不做物理删除。
    category.is_deleted = True
    category.last_update_user = "api"
    await session.commit()
    return None
