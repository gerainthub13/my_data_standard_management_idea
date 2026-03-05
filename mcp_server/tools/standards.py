"""
tools/standards.py — 数据标准管理工具

数据标准是 DSMS 的核心实体，具有状态流转和版本控制机制。

**状态值说明**（status 字段）：
  0 = draft（草稿）— 初始状态，可编辑
  1 = published（已发布）— 正式生效，不可直接编辑；如需修改需创建新 revision
  2 = retired（退役）— 已退役，仍可编辑后重新发布
  3 = deprecated（已删除）— 软删除状态，is_deleted=true
  4 = other（其他）

**典型工作流（创建并发布标准）**：
  1. list_categories → 获取分类 ID
  2. keyword_search_standards / vector_search_standards → 确认同义标准不存在
  3. create_standard → 创建草稿
  4. update_standard → 补充详细信息（可选）
  5. publish_standard → 发布
  6. bind_standard_codelist → 绑定码表（可选，需码表已发布）

**版本更新流（更新已发布标准）**：
  1. get_standard_detail → 获取当前版本信息
  2. create_standard_revision → 基于当前版本创建新草稿
  3. update_standard（新版本 ID）→ 修改内容
  4. publish_standard（新版本 ID）→ 发布新版本（旧版本自动失去 is_latest）
"""
from __future__ import annotations

from typing import Any

from mcp_server.http_client import api_delete, api_get, api_patch, api_post, api_put


async def list_standards(
    page: int = 1,
    page_size: int = 20,
    code: str | None = None,
    name: str | None = None,
    status: int | None = None,
    category_id: int | None = None,
    is_latest: bool | None = None,
) -> dict | str:
    """
    分页查询数据标准列表。

    **使用场景**：
    - 枚举所有标准做批量查看（建议先用搜索工具定位后再用此接口查详情）；
    - 按状态或分类筛选特定范围内的标准；
    - 查看某分类下的全部标准清单。

    **与搜索工具的区别**：
    - list_standards：精确字段过滤 + 分页，不支持模糊搜索；
    - keyword_search_standards：多字段模糊匹配，适合搜索场景；
    - vector_search_standards：语义搜索，适合模糊需求描述。

    **参数说明**：
    - code: 精确匹配编码（非模糊），如 "STD_HR_001"；
    - name: 精确匹配名称（非模糊）；
    - status: 状态过滤（0/1/2/3/4），不填则返回所有未删除；
    - category_id: 按分类 ID 过滤；
    - is_latest: true=仅最新版本，false=仅历史版本，null=全部。

    **返回**：{ items: [StandardOut], total, page, page_size }
    """
    params = {
        "page": page,
        "page_size": page_size,
        "code": code,
        "name": name,
        "status": status,
        "category_id": category_id,
        "is_latest": is_latest,
    }
    return await api_get("/api/v1/standards", params)


async def get_standard_detail(
    standard_id: str,
    lang: str | None = None,
) -> dict | str:
    """
    查询单条数据标准的完整详情。

    **使用场景**：
    - 搜索或列表后，获取标准的完整信息（含多语言翻译和绑定码表摘要）；
    - 在进行状态操作（发布/更新）前，查看当前状态确认可行性；
    - 查看标准绑定的码表信息。

    **参数说明**：
    - standard_id: 标准的 UUID 字符串（从搜索或列表结果的 id 字段获取）；
    - lang: 多语言内容优先使用的语言（zh/en/ja），未指定时使用系统默认语言。
            若该语言无翻译内容，自动回退到默认语言。

    **返回**：StandardDetailOut
    包含：id, code, name, description, category_id, status, version, is_latest,
          translations（多语言内容列表）, code_list（绑定码表摘要，无绑定则null）,
          extattributes（扩展属性 JSON）, created_at, updated_at
    """
    params = {}
    if lang:
        params["lang"] = lang
    return await api_get(f"/api/v1/standards/{standard_id}", params or None)


async def get_standard_history(code: str) -> list | str:
    """
    查询数据标准的所有历史版本。

    **使用场景**：
    - 查看某标准从 v1 至今的所有版本演变；
    - 对比不同版本内容（结合 get_standard_detail 查各版本详情）；
    - 确认需要基于哪个版本创建 revision。

    **参数说明**：
    - code: 标准编码（如 "STD_HR_001"），注意是 code 字段而非 id。

    **返回**：[StandardOut]，按 version 倒序（最新版本在前）。
    每条包含：id, code, version, status, is_latest 等基础字段。
    """
    return await api_get(f"/api/v1/standards/{code}/history")


async def create_standard(
    code: str,
    name: str,
    description: str | None = None,
    category_id: int | None = None,
    extattributes: dict[str, Any] | None = None,
    translations: list[dict] | None = None,
) -> dict | str:
    """
    创建新数据标准（草稿状态，version=1）。

    **使用场景**：仅在确认同义标准不存在后创建，建议先调用搜索工具排查。

    **前置步骤建议**：
    1. 调用 keyword_search_standards 或 vector_search_standards 确认无重复标准；
    2. 调用 list_categories 获取有效的 category_id；
    3. 确认 code 编码规范（仅允许字母、数字、下划线、短横线，示例：STD_HR_001）。

    **参数说明**：
    - code: 标准编码（唯一标识，最长50字符，仅允许字母/数字/下划线/短横线）。
            同 code 的 version=1 只能存在一条；已有 version=1 时需用 create_standard_revision；
    - name: 标准名称（最长200字符，不可含特殊符号）；
    - description: 标准说明（选填，建议填写有助于向量搜索语义准确性）；
    - category_id: 所属分类 ID（选填，建议填写以便分类管理）；
    - extattributes: 扩展属性（JSON 对象，选填，存储业务自定义字段）；
    - translations: 多语言内容（选填），格式：
        [{"fieldname": "name", "language": "en", "content": "Employee Name"},
         {"fieldname": "description", "language": "en", "content": "..."}]

    **返回**：创建成功的 StandardOut（含 id，status=0 draft）。
    创建后自动触发 embedding 向量构建任务（异步，不影响返回速度）。
    """
    body: dict[str, Any] = {"code": code, "name": name}
    if description is not None:
        body["description"] = description
    if category_id is not None:
        body["category_id"] = category_id
    if extattributes is not None:
        body["extattributes"] = extattributes
    if translations is not None:
        body["translations"] = translations
    return await api_post("/api/v1/standards", body)


async def update_standard(
    standard_id: str,
    name: str | None = None,
    description: str | None = None,
    category_id: int | None = None,
    extattributes: dict[str, Any] | None = None,
    translations: list[dict] | None = None,
) -> dict | str:
    """
    更新数据标准内容（仅允许草稿或退役状态）。

    **使用场景**：
    - 补充/修正草稿标准的名称、说明等信息；
    - 更新多语言翻译内容；
    - 注意：已发布（status=1）的标准不可直接更新，需先调用 create_standard_revision
           创建新版本，再更新新版本内容。

    **参数说明**：
    - standard_id: 标准 UUID（必填）；
    - name/description/category_id/extattributes: 选填，传则更新，不传则保持原值；
    - translations: 多语言内容，传则覆盖更新（upsert），格式同 create_standard。

    **限制**：
    - status=1（已发布）→ 报错，需先 create_standard_revision；
    - status=3（已删除）→ 报错。

    **返回**：更新后的 StandardOut。更新后自动触发 embedding 重建。
    """
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if category_id is not None:
        body["category_id"] = category_id
    if extattributes is not None:
        body["extattributes"] = extattributes
    if translations is not None:
        body["translations"] = translations
    return await api_put(f"/api/v1/standards/{standard_id}", body)


async def publish_standard(standard_id: str) -> dict | str:
    """
    发布数据标准版本。

    **使用场景**：
    - 草稿标准完善后，正式发布使其生效；
    - 发布后同 code 下原 is_latest=true 的版本会自动设为 is_latest=false；
    - 发布后该版本成为最新发布版本（is_latest=true, status=1）。

    **前置条件**：标准不可处于已删除状态（status=3）。

    **参数说明**：
    - standard_id: 要发布的标准 UUID。

    **返回**：发布后的 StandardOut（status=1, is_latest=true）。
    """
    return await api_patch(f"/api/v1/standards/{standard_id}/publish")


async def update_standard_status(
    standard_id: str,
    status: int,
) -> dict | str:
    """
    直接更新标准状态（精细状态控制）。

    **使用场景**：
    - 将已发布标准标为退役（status=2）；
    - 在不通过 publish_standard 接口的情况下直接设置状态；
    - 注意：当 status=1（published）时，此接口会自动执行发布一致性逻辑
           （与 publish_standard 等效）。

    **参数说明**：
    - standard_id: 标准 UUID；
    - status: 目标状态值：
        0 = draft（草稿）
        1 = published（发布，等同于调用 publish_standard）
        2 = retired（退役）
        4 = other

    **返回**：更新后的 StandardOut。
    """
    return await api_patch(f"/api/v1/standards/{standard_id}/status", {"status": status})


async def create_standard_revision(standard_id: str) -> dict | str:
    """
    基于现有标准创建新版本（revision）。

    **使用场景**：
    - 需要修改已发布标准时，不能直接编辑，需先创建新版本；
    - 新版本 version 自动在同 code 最大版本基础上 +1；
    - 新版本为草稿状态（status=0），内容复制自源版本（不含 embedding）。

    **典型流程**：
    1. create_standard_revision(已发布版本的 standard_id)
    2. update_standard(新版本 ID)  → 修改内容
    3. publish_standard(新版本 ID) → 发布新版本

    **参数说明**：
    - standard_id: 作为基础的标准 UUID（可以是任何未删除版本）。

    **返回**：新建的 StandardOut（status=0 draft，version=N+1）。
    """
    return await api_post(f"/api/v1/standards/{standard_id}/revision")


async def delete_standard(standard_id: str) -> dict | str:
    """
    软删除数据标准（is_deleted=true, status=3，不可恢复）。

    **使用场景**：
    - 删除错误创建的草稿标准；
    - 废弃已退役的历史版本；
    - 注意：软删除不影响历史数据追溯，记录仍在数据库中，只是在列表中被过滤。

    **删除后影响**：
    - is_deleted=true, status=3, is_latest=false；
    - 已绑定的码表关系不会自动解绑（但该版本已不在正常查询范围内）。

    **参数说明**：
    - standard_id: 要删除的标准 UUID。

    **返回**：{ ok: true } 或错误说明。
    """
    return await api_delete(f"/api/v1/standards/{standard_id}")


async def get_standard_codelist_binding(standard_id: str) -> dict | str:
    """
    查询标准绑定的码表（标准代码列表）摘要。

    **使用场景**：
    - 查看某标准当前是否绑定了码表，以及绑定的码表信息；
    - 在绑定操作前确认当前绑定状态；
    - 配合 get_code_list_detail 获取完整码表内容（用到返回的 code_list_id）。

    **参数说明**：
    - standard_id: 标准 UUID。

    **返回**：{ standard_id, code_list_id(null if unbound), code_list: { id, list_code, name, version, status, is_latest } }
    """
    return await api_get(f"/api/v1/standards/{standard_id}/code-list")


async def bind_standard_codelist(
    standard_id: str,
    code_list_id: str | None,
) -> dict | str:
    """
    绑定或解绑标准与码表的关联关系。

    **使用场景**：
    - 将枚举型字段的可选值集合（码表）与数据标准绑定，明确该标准的取值范围；
    - 一条标准最多绑定一个码表版本（每次绑定会覆盖旧绑定）；
    - 传 code_list_id=null 表示解绑；
    - 仅允许绑定状态为已发布（status=1）且 is_latest=true 的码表版本。

    **前置步骤建议**：
    1. 调用 search_code_lists 或 list_code_lists(bindable=true) 找到可绑定码表；
    2. 确认目标码表 status=1 且 is_latest=true；
    3. 调用此工具完成绑定。

    **参数说明**：
    - standard_id: 标准 UUID（必填）；
    - code_list_id: 要绑定的码表 UUID；传 null 表示解绑。

    **返回**：{ standard_id, code_list_id, code_list: {...} }
    """
    return await api_put(
        f"/api/v1/standards/{standard_id}/code-list",
        {"code_list_id": code_list_id},
    )
