"""
tools/categories.py — 分类管理工具

分类是数据标准的组织结构，支持多级父子树（parent_id 引用自身）。
所有写操作均需分类处于"未删除"状态。system 类型分类不可修改/删除。

典型调用场景：
  1. 创建标准前，先调用 list_categories 获取可用分类 ID；
  2. 若无合适分类，先调用 create_category，再创建标准；
  3. 删除分类前需确认无子分类（API 会拒绝有子节点的删除请求）。
"""
from __future__ import annotations

from mcp_server.http_client import api_delete, api_get, api_post, api_put


async def list_categories(
    keyword: str | None = None,
    category_id: int | None = None,
    parent_id: int | None = None,
    scope: str | None = None,
    allow_empty_keyword: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict | str:
    """
    查询分类列表。

    **使用场景**：
    - 获取所有可用分类，以便为数据标准选择合适的 category_id；
    - 按关键词搜索特定分类；
    - 按 parent_id 列出子分类。

    **参数说明**：
    - keyword: 分类名称关键词（模糊匹配）。若未提供 category_id，默认必须提供 keyword
              或将 allow_empty_keyword 设为 true；
    - category_id: 精确查询单条分类（按 ID），此时忽略其他过滤参数；
    - parent_id: 仅返回指定父分类下的子分类；
    - scope: 过滤分类用途，可选值 standard（数据标准）/metric（指标）/bizdict（业务词典）；
    - allow_empty_keyword: 设为 true 时允许不提供关键词，返回分页全量列表；
    - page/page_size: 分页参数。

    **返回**：{ items: [...], total, page, page_size }
    每条分类包含：id, name, parent_id, category_type(system/custom), scope, created_at, updated_at
    """
    params: dict = {
        "keyword": keyword,
        "id": category_id,
        "parent_id": parent_id,
        "scope": scope,
        "allow_empty_keyword": str(allow_empty_keyword).lower() if allow_empty_keyword else None,
        "page": page,
        "page_size": page_size,
    }
    return await api_get("/api/v1/categories", params)


async def create_category(
    name: str,
    parent_id: int | None = None,
    scope: str = "standard",
) -> dict | str:
    """
    创建自定义分类。

    **使用场景**：
    - 在为数据标准指定分类时，若现有分类不满足需求，先创建新分类；
    - 建立多级分类体系（先创建父分类，再创建子分类并传入 parent_id）。

    **参数说明**：
    - name: 分类名称（最长200字符，不可含非法字符）。同一父分类下名称必须唯一；
    - parent_id: 父分类 ID（选填）。顶级分类不填或传 null。
                 父分类必须存在且未被删除；
    - scope: 分类适用范围：standard（默认）/ metric / bizdict。

    **前置条件**：若需要子分类，父分类必须已存在（可先调用 list_categories 确认）。

    **返回**：创建成功的分类对象（含 id）。
    """
    body = {"name": name, "scope": scope}
    if parent_id is not None:
        body["parent_id"] = parent_id
    return await api_post("/api/v1/categories", body)


async def update_category(
    category_id: int,
    name: str | None = None,
    parent_id: int | None = None,
    scope: str | None = None,
) -> dict | str:
    """
    更新分类信息（仅限 custom 类型分类）。

    **使用场景**：
    - 更正分类名称或调整分类归属（parent_id）；
    - 注意：system 类型分类（如系统预置分类）不可修改，API 会返回 403 错误。

    **参数说明**：
    - category_id: 要更新的分类 ID（必填）；
    - name: 新名称（选填，传则更新）；
    - parent_id: 新父分类 ID（选填）。不能将分类移动到自身或其子孙节点下；
    - scope: 新 scope 值（选填）。

    **返回**：更新后的分类对象。
    """
    body: dict = {}
    if name is not None:
        body["name"] = name
    if parent_id is not None:
        body["parent_id"] = parent_id
    if scope is not None:
        body["scope"] = scope
    return await api_put(f"/api/v1/categories/{category_id}", body)


async def delete_category(category_id: int) -> dict | str:
    """
    软删除分类（不可恢复，is_deleted=true）。

    **使用场景**：
    - 删除已废弃的分类节点；
    - 注意以下限制（删除前请确认）：
      1. 存在子分类时拒绝删除——需先删除所有子分类；
      2. system 类型分类不允许删除；
      3. 被数据标准引用的分类仍可删除，但现有引用标准的 category_id 不会自动清
         空（不影响现有标准功能）。

    **参数说明**：
    - category_id: 要删除的分类 ID。

    **返回**：{ ok: true } 或错误说明。
    """
    return await api_delete(f"/api/v1/categories/{category_id}")
