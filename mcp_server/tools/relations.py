"""
tools/relations.py — 数据标准关系管理工具

标准关系用于描述数据标准之间或标准与外部资产（表、列等）之间的关联。
关系是有向的（sourceid → targetid），支持多种关系类型。

**关系类型（reltype）**：
  parentchild   — 父子继承关系（上下位概念）
  maptotable    — 标准映射到物理数据表
  standardlink  — 标准间的横向关联（参照、补充等）
  modelmapping  — 标准映射到数据模型字段

**目标类型（targettype）**：
  internalstd   — 目标为系统内另一条数据标准
  externalstd   — 目标为外部标准（ISO、GB 等）
  table         — 目标为数据库表
  column        — 目标为数据库字段

**使用建议**：
  - 创建关系前，建议先用 get_standard_detail 或 list_standards 确认源标准存在；
  - 关系不做软删除，delete_standard_relation 为物理删除。
"""
from __future__ import annotations

from mcp_server.http_client import api_delete, api_get, api_post


async def list_standard_relations(standard_id: str) -> list | str:
    """
    查询数据标准的所有关系（出度 + 入度）。

    **使用场景**：
    - 查看某标准与其他标准或外部资产的所有关联关系；
    - 分析标准的上下游依赖（internalstd 关系）；
    - 查看标准对应的物理表/字段映射（maptotable/modelmapping）。

    **参数说明**：
    - standard_id: 标准 UUID（查询该标准为 source 或 target 的全部关系）。

    **返回**：[RelationOut]
    每条关系包含：id, sourceid, sourcever, targetid, targetver,
                 reltype, targettype, relstatus
    sourceid=standard_id 时为出度关系；targetid=standard_id 时为入度关系。
    """
    return await api_get(f"/api/v1/standards/{standard_id}/relations")


async def create_standard_relation(
    standard_id: str,
    targetid: str,
    reltype: str,
    targettype: str,
    targetver: str | None = None,
    relstatus: int = 0,
) -> dict | str:
    """
    创建数据标准关系（有向边）。

    **使用场景**：
    - 建立标准间的父子关系（如"员工编号"是"人员标识符"的子概念）；
    - 将标准映射到物理表/字段（用于血缘追踪）；
    - 标记标准与外部法规/行业标准的对应关系。

    **注意**：同一组合（sourceid+targetid+targetver+reltype+targettype）不可重复，
    重复创建会返回 409 错误，可用 list_standard_relations 检查是否已存在。

    **参数说明**：
    - standard_id: 源标准 UUID（必填）；
    - targetid: 目标对象 ID（字符串，最长100字符）——
        若 targettype=internalstd：填目标标准的 UUID；
        若 targettype=table/column：填表名或字段全限定名；
        若 targettype=externalstd：填外部标准编号；
    - reltype: 关系类型（parentchild/maptotable/standardlink/modelmapping）；
    - targettype: 目标类型（internalstd/externalstd/table/column）；
    - targetver: 目标版本标识（选填，字符串如 "v1"、"1.0"）；
    - relstatus: 关系有效性状态（0=有效/生效，1=无效/草稿，默认0）。

    **返回**：创建成功的 RelationOut（含自增 id）。
    """
    body: dict = {
        "targetid": targetid,
        "reltype": reltype,
        "targettype": targettype,
        "relstatus": relstatus,
    }
    if targetver is not None:
        body["targetver"] = targetver
    return await api_post(f"/api/v1/standards/{standard_id}/relations", body)


async def delete_standard_relation(rel_id: int) -> dict | str:
    """
    删除标准关系记录（物理删除，不可恢复）。

    **使用场景**：
    - 删除错误创建的关系；
    - 清理不再有效的映射关系。

    **注意**：此操作为物理删除，执行后不可恢复。请先确认关系 ID 正确。
    关系 ID 可从 list_standard_relations 返回结果的 id 字段获取。

    **参数说明**：
    - rel_id: 关系记录的整数 ID（从 list_standard_relations 获取）。

    **返回**：{ ok: true } 或错误说明。
    """
    return await api_delete(f"/api/v1/standards/relations/{rel_id}")
