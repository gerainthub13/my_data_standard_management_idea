"""
tools/code_lists.py — 标准代码列表（码表）管理工具

码表（StandardCodeList）是数据标准的取值集合，用于约束枚举型字段的可选值。
例如："员工类型" 标准的码表可能包含：01=全职、02=兼职、03=实习。

**码表结构**：
  - 主表（StandardCodeList）：list_code、name、purpose、version、status、is_latest
  - 子项（StandardCodeItem）：item_code（编码）、item_name（名称）、meaning（含义说明）

**状态值（status）**：
  0 = draft（草稿）— 可编辑子项
  1 = published（已发布）— 可被标准绑定，不可编辑子项
  2 = retired（退役）
  3 = deprecated（已删除，软删）

**典型工作流（创建并发布码表）**：
  1. search_code_lists → 确认无重复码表
  2. create_code_list（含 items）→ 创建草稿（或先创建主表再替换子项）
  3. replace_code_list_items → 批量写入/调整子项（草稿阶段）
  4. publish_code_list → 发布（之后不可编辑子项）
  5. [在标准工具中] bind_standard_codelist → 将码表绑定到数据标准

**版本更新流**：
  1. create_code_list_revision(已发布码表 ID) → 生成新草稿版本
  2. replace_code_list_items(新版本 ID) → 修改子项
  3. publish_code_list(新版本 ID) → 发布新版本
"""
from __future__ import annotations

from typing import Any

from mcp_server.http_client import api_delete, api_get, api_patch, api_post, api_put


async def list_code_lists(
    page: int = 1,
    page_size: int = 20,
    list_code: str | None = None,
    name: str | None = None,
    status: int | None = None,
    is_latest: bool | None = None,
    bindable: bool = False,
) -> dict | str:
    """
    分页查询码表列表。

    **使用场景**：
    - 枚举所有可用码表；
    - 使用 bindable=true 仅返回可绑定版本（已发布 + is_latest=true），
      用于在标准绑定操作前查找符合条件的码表；
    - 按 list_code 精确查找特定码表的版本列表。

    **参数说明**：
    - list_code: 精确匹配码表编码（如 "CL_EMP_TYPE"）；
    - name: 精确匹配码表名称；
    - status: 状态过滤（0草稿/1已发布/2退役/3已删除）；
    - is_latest: true/false/null；
    - bindable: true=仅返回 status=1 且 is_latest=true 的可绑定版本。

    **返回**：{ items: [CodeListOut], total, page, page_size }
    """
    params = {
        "page": page,
        "page_size": page_size,
        "list_code": list_code,
        "name": name,
        "status": status,
        "is_latest": is_latest,
        "bindable": str(bindable).lower(),
    }
    return await api_get("/api/v1/code-lists", params)


async def search_code_lists(
    query: str,
    top_k: int = 20,
    only_bindable: bool = False,
) -> dict | str:
    """
    关键词搜索码表（主表字段 + 子项字段同时检索）。

    **使用场景**：
    - 通过关键词查找合适的码表，以便绑定到数据标准；
    - 搜索码表名称、用途说明，或码表子项的编码/名称/含义；
    - 使用 only_bindable=true 限定只返回可绑定版本（避免返回草稿）。

    **与 list_code_lists 的区别**：
    - search_code_lists：多字段模糊匹配（含子项字段），适合搜索场景；
    - list_code_lists：精确字段过滤 + 分页，适合枚举和精确查找。

    **参数说明**：
    - query: 搜索关键词（必填，至少1字符），同时匹配主表和子项字段；
    - top_k: 最多返回条数（1-200，默认20）；
    - only_bindable: true=仅返回 status=1 且 is_latest=true 的可绑定版本。

    **返回**：{ items: [{ id, list_code, name, purpose, version, status, is_latest, matched_by }] }
    matched_by 字段说明匹配来源：["list"]（主表匹配）/ ["item"]（子项匹配）/ ["list","item"]（两者均匹配）
    """
    body: dict[str, Any] = {"query": query, "top_k": top_k, "only_bindable": only_bindable}
    return await api_post("/api/v1/code-lists/search", body)


async def get_code_list_detail(
    code_list_id: str,
    include_items: bool = True,
) -> dict | str:
    """
    查询码表详情（含子项列表）。

    **使用场景**：
    - 查看码表的完整内容（主表信息 + 全部码值子项）；
    - 在标准绑定码表前确认码表内容是否正确；
    - 查看码表当前 status/version/is_latest 等状态。

    **参数说明**：
    - code_list_id: 码表 UUID（从搜索或列表结果中获取）；
    - include_items: true（默认）=包含子项列表，false=只返回主表信息。

    **返回**：CodeListDetailOut
    包含：id, list_code, name, purpose, status, version, is_latest,
          items: [{ id, item_code, item_name, meaning, sort_order }]（include_items=true时）
    """
    params = {"include_items": str(include_items).lower()}
    return await api_get(f"/api/v1/code-lists/{code_list_id}", params)


async def get_code_list_items(
    code_list_id: str,
    page: int = 1,
    page_size: int = 50,
    keyword: str | None = None,
) -> dict | str:
    """
    分页查询码表子项（码值列表）。

    **使用场景**：
    - 当码表子项数量较多时，分页查看而非一次性加载（get_code_list_detail 子项无分页）；
    - 按关键词过滤子项（item_code/item_name/meaning 模糊匹配）；
    - 确认特定码值是否存在（如 "01" 是否已在码表中）。

    **参数说明**：
    - code_list_id: 码表 UUID；
    - page/page_size: 分页（每页最多500条）；
    - keyword: 子项关键词过滤（选填）。

    **返回**：{ items: [CodeItemOut], total, page, page_size }
    """
    params: dict = {"page": page, "page_size": page_size}
    if keyword:
        params["keyword"] = keyword
    return await api_get(f"/api/v1/code-lists/{code_list_id}/items", params)


async def get_code_list_history(list_code: str) -> list | str:
    """
    查询码表的所有历史版本。

    **使用场景**：
    - 查看某码表从 v1 至今的所有版本演变；
    - 确认当前最新发布版本号，决定是否需要创建新版本。

    **参数说明**：
    - list_code: 码表编码（如 "CL_EMP_TYPE"），注意是 list_code 字段而非 id。

    **返回**：[CodeListOut]，按 version 倒序（最新版本在前）。
    """
    return await api_get(f"/api/v1/code-lists/code/{list_code}/history")


async def get_code_list_bindings(
    code_list_id: str,
    page: int = 1,
    page_size: int = 20,
    published_only: bool = False,
) -> dict | str:
    """
    查询引用该码表的所有数据标准。

    **使用场景**：
    - 在删除或更新码表版本前，确认有哪些标准在使用该码表（影响评估）；
    - 查找使用某码表的全部标准（反向追溯）。

    **参数说明**：
    - code_list_id: 码表 UUID；
    - published_only: true=仅返回已发布标准引用，false=返回所有状态标准。

    **返回**：{ items: [{ id, code, name, version, status, is_latest }], total, page, page_size }
    """
    params: dict = {
        "page": page,
        "page_size": page_size,
        "published_only": str(published_only).lower(),
    }
    return await api_get(f"/api/v1/code-lists/{code_list_id}/bindings", params)


async def create_code_list(
    list_code: str,
    name: str,
    purpose: str | None = None,
    items: list[dict] | None = None,
) -> dict | str:
    """
    创建新码表（草稿状态，version=1）。

    **使用场景**：用于创建新的枚举取值集合，通常在为数据标准提供可选值范围时使用。

    **前置步骤建议**：
    1. 调用 search_code_lists 确认无重复码表；
    2. 准备好所有码值子项（items）可一次性创建，也可后续用 replace_code_list_items 更新。

    **参数说明**：
    - list_code: 码表编码（唯一，最长50字符，仅允许字母/数字/下划线/短横线）；
    - name: 码表名称；
    - purpose: 用途说明（选填，有助于 LLM 理解该码表用途）；
    - items: 初始子项列表（选填），格式：
        [{"item_code": "01", "item_name": "全职", "meaning": "全日制正式员工", "sort_order": 1},
         {"item_code": "02", "item_name": "兼职", "sort_order": 2}]
        同一码表内 item_code 必须唯一。

    **返回**：创建成功的 CodeListOut（含 id，status=0 draft）。
    """
    body: dict[str, Any] = {"list_code": list_code, "name": name}
    if purpose is not None:
        body["purpose"] = purpose
    if items is not None:
        body["items"] = items
    return await api_post("/api/v1/code-lists", body)


async def update_code_list(
    code_list_id: str,
    name: str | None = None,
    purpose: str | None = None,
) -> dict | str:
    """
    更新码表主表信息（仅草稿状态可编辑）。

    **使用场景**：修正码表名称或用途说明。
    注意：子项内容的修改请使用 replace_code_list_items，此接口仅更新主表字段。

    **参数说明**：
    - code_list_id: 码表 UUID；
    - name: 新名称（选填）；
    - purpose: 新用途说明（选填）。

    **限制**：status 不为 0（草稿）时返回错误，需先 create_code_list_revision。

    **返回**：更新后的 CodeListOut。
    """
    body: dict = {}
    if name is not None:
        body["name"] = name
    if purpose is not None:
        body["purpose"] = purpose
    return await api_put(f"/api/v1/code-lists/{code_list_id}", body)


async def replace_code_list_items(
    code_list_id: str,
    items: list[dict],
) -> dict | str:
    """
    批量替换码表子项（覆盖写，仅草稿状态可操作）。

    **使用场景**：
    - 完整定义或更新码表的枚举值集合；
    - 此操作为覆盖式：旧子项列表被逻辑删除，以 items 参数完整替换；
    - 适合从外部系统导入完整码值列表。

    **注意**：传空列表 [] 会清空所有子项；请确保 items 包含所有期望保留的子项。

    **前置条件**：码表必须处于草稿状态（status=0）。

    **参数说明**：
    - code_list_id: 码表 UUID（必须为草稿状态）；
    - items: 完整子项列表（覆盖写），格式：
        [{"item_code": "01", "item_name": "名称", "meaning": "含义", "sort_order": 1}]
        同一码表内 item_code 必须唯一；sort_order 控制排序（升序）。

    **返回**：替换后的完整子项列表 { items, total, page, page_size }。
    """
    return await api_put(
        f"/api/v1/code-lists/{code_list_id}/items",
        {"items": items},
    )


async def publish_code_list(code_list_id: str) -> dict | str:
    """
    发布码表版本。

    **使用场景**：
    - 码表子项已确认后，发布使其可被数据标准绑定；
    - 发布后 is_latest=true，同 list_code 下原 is_latest=true 的版本自动失效；
    - 发布后该版本不可再编辑子项。

    **前置条件**：码表不可处于已删除状态（status=3）。

    **返回**：发布后的 CodeListOut（status=1, is_latest=true）。
    """
    return await api_patch(f"/api/v1/code-lists/{code_list_id}/publish")


async def update_code_list_status(
    code_list_id: str,
    status: int,
) -> dict | str:
    """
    直接更新码表状态（精细状态控制）。

    **使用场景**：
    - 将已发布码表标为退役（status=2）；
    - 注意：当 status=1 时，等同于调用 publish_code_list（触发发布一致性逻辑）。

    **参数说明**：
    - code_list_id: 码表 UUID；
    - status: 0=草稿/1=发布/2=退役/4=其他。

    **返回**：更新后的 CodeListOut。
    """
    return await api_patch(
        f"/api/v1/code-lists/{code_list_id}/status",
        {"status": status},
    )


async def create_code_list_revision(code_list_id: str) -> dict | str:
    """
    基于现有码表版本创建新版本（revision）。

    **使用场景**：
    - 需要修改已发布码表的子项内容时，必须先创建新版本；
    - 新版本复制源版本的全部生效子项，version 自动 +1，状态为草稿。

    **典型流程**：
    1. create_code_list_revision(已发布码表 ID)
    2. replace_code_list_items(新版本 ID, 新子项列表)
    3. publish_code_list(新版本 ID)

    **参数说明**：
    - code_list_id: 源码表 UUID（任何未删除版本均可作为基础）。

    **返回**：新建的 CodeListOut（status=0 draft，version=N+1）。
    """
    return await api_post(f"/api/v1/code-lists/{code_list_id}/revision")


async def delete_code_list(code_list_id: str) -> dict | str:
    """
    软删除码表（is_deleted=true，不可恢复）。

    **使用场景**：删除错误创建的码表，或废弃不再使用的历史版本。

    **限制**：若该码表被已发布的数据标准引用，则无法删除（API 返回 409 错误）。
    需先解绑所有引用标准（调用标准工具的 bind_standard_codelist 传 null），
    再执行删除。可用 get_code_list_bindings 查询当前引用情况。

    **返回**：{ ok: true } 或错误说明。
    """
    return await api_delete(f"/api/v1/code-lists/{code_list_id}")
