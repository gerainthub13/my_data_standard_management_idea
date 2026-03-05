from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import StandardSearchRequest, StandardSearchResponse
from app.services.code_lists import get_standard_code_link_map
from app.services.search import keyword_filter, vector_search


# 搜索 API
router = APIRouter(prefix="/api/v1/standards", tags=["search"])


@router.post(
    "/search",
    response_model=StandardSearchResponse,
    summary="组合搜索",
    description="支持向量检索和关键词检索两种模式，均默认只检索已发布且最新版本。",
)
async def search_standards(
    payload: StandardSearchRequest,
    session: AsyncSession = Depends(get_session),
):
    # 组合搜索：向量检索优先；关闭向量时回退关键词过滤。
    items = []
    standard_ids = []
    standards_cache: dict[str, dict] = {}
    if payload.use_vector:
        results = await vector_search(
            session,
            payload.query,
            payload.lang,
            payload.top_k,
            int(payload.status) if payload.status is not None else None,
            payload.is_latest,
        )
        for standard, distance in results:
            standard_ids.append(standard.id)
            standards_cache[str(standard.id)] = {
                "id": standard.id,
                "code": standard.code,
                "name": standard.name,
                "description": standard.description,
                "version": standard.version,
                "status": standard.status,
                "is_latest": standard.is_latest,
                "created_at": standard.created_at,
                "updated_at": standard.updated_at,
                "score": 1 - distance,
            }
    else:
        results = await keyword_filter(
            session,
            payload.query,
            payload.top_k,
            int(payload.status) if payload.status is not None else None,
            payload.is_latest,
        )
        for standard in results:
            standard_ids.append(standard.id)
            standards_cache[str(standard.id)] = {
                "id": standard.id,
                "code": standard.code,
                "name": standard.name,
                "description": standard.description,
                "version": standard.version,
                "status": standard.status,
                "is_latest": standard.is_latest,
                "created_at": standard.created_at,
                "updated_at": standard.updated_at,
                "score": None,
            }

    has_code_set = await get_standard_code_link_map(session, standard_ids)
    for standard_id in standard_ids:
        key = str(standard_id)
        payload_item = standards_cache.get(key)
        if not payload_item:
            continue
        payload_item["has_code_list"] = standard_id in has_code_set
        items.append(payload_item)
    return StandardSearchResponse(items=items)
