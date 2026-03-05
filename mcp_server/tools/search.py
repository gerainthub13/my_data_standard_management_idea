"""
tools/search.py — 数据标准搜索工具

本模块提供两种互补的搜索方式，适用于不同场景：

┌─────────────────────────────────────────────────────────────────────────┐
│  工具                       │ 核心技术  │ 典型场景                       │
├─────────────────────────────────────────────────────────────────────────┤
│ keyword_search_standards    │ SQL ILIKE │ 已知名称/编码，精确定位；       │
│                             │ 模糊匹配  │ 验证特定标准是否存在           │
├─────────────────────────────────────────────────────────────────────────┤
│ vector_search_standards     │ pgvector  │ 用自然语言描述需求，找近似标   │
│                             │ 余弦相似  │ 准；分析现有标准覆盖范围；     │
│                             │           │ 相似标准排查与去重             │
└─────────────────────────────────────────────────────────────────────────┘

选择依据：
- 已有具体名称/关键词 → 优先 keyword_search_standards
- 描述需求/概念，不确定标准名称 → 优先 vector_search_standards
- vector_search 依赖 embedding 服务在线；keyword_search 无此依赖
"""
from __future__ import annotations

from mcp_server.http_client import api_post
from mcp_server.config import get_settings


async def keyword_search_standards(
    query: str,
    top_k: int = 10,
    status: int | None = 1,
    is_latest: bool | None = True,
) -> dict | str:
    """
    关键词检索数据标准（SQL ILIKE 模糊匹配）。

    **核心特点**：
    - 在标准的 code（编码）、name（名称）、description（说明）三个字段做模糊匹配；
    - 无需 embedding 服务，随时可用；
    - 结果无相似度评分（score=null），按 code 字典序排序；
    - 适合"已知部分名称/编码"的精确定位场景。

    **使用场景举例**：
    - "查找编码包含 'HR' 的标准" → query="HR"
    - "看看有没有'员工姓名'相关标准" → query="员工姓名"
    - "查 STD_EMP 这个编码的标准" → query="STD_EMP"

    **注意**：若结果为空，考虑换用 vector_search_standards 做语义检索。

    **参数说明**：
    - query: 搜索关键词（必填，最短1字符）；
    - top_k: 最多返回条数（1-100，默认10）；
    - status: 状态过滤：0=草稿, 1=已发布（默认）, 2=退役, 3=已删除, 4=其他, null=不过滤；
    - is_latest: true=仅最新版本（默认）, false=含历史版本, null=不过滤。

    **返回**：{ items: [{ id, code, name, description, version, status, is_latest,
                         has_code_list, score(null) }] }
    """
    body = {
        "query": query,
        "use_vector": False,
        "top_k": top_k,
        "lang": get_settings().server.default_language,
    }
    if status is not None:
        body["status"] = status
    if is_latest is not None:
        body["is_latest"] = is_latest
    return await api_post("/api/v1/standards/search", body)


async def vector_search_standards(
    query: str,
    lang: str | None = None,
    top_k: int = 10,
    status: int | None = 1,
    is_latest: bool | None = True,
) -> dict | str:
    """
    向量语义检索数据标准（pgvector 余弦相似度）。

    **核心特点**：
    - 将 query 转为 embedding 向量后，与数据库中已有标准向量做余弦距离计算；
    - 能识别语义相似但措辞不同的标准（如"雇员"和"员工"会被认为近似）；
    - 结果包含 score（0~1，越接近1越相似），按相似度降序排列；
    - 依赖 LM Studio embedding 服务在线（DSMS API 后端配置），若服务不可用会报错。

    **使用场景举例**：
    - "用自然语言描述来找标准：查找描述员工薪资待遇相关的标准"
    - "我想知道现有标准是否已覆盖'产品质量等级'这个概念"
    - "找出与'部门编号'语义最相近的5条标准"（用于相似标准排查）

    **与关键词搜索的区别**：
    - 关键词搜索：精确匹配字符串 → 适合已知具体词汇
    - 向量搜索：语义理解 → 适合模糊需求描述和覆盖范围分析

    **参数说明**：
    - query: 搜索描述（必填，建议用完整短语或句子，语义越丰富结果越准确）；
    - lang: 向量检索使用的语言（zh/en/ja，默认读取 config.toml 中 default_language）；
    - top_k: 最多返回条数（1-100，默认10）；
    - status: 状态过滤（同关键词搜索）；
    - is_latest: 版本过滤（同关键词搜索）。

    **返回**：{ items: [{ id, code, name, description, version, status, is_latest,
                         has_code_list, score(float 0~1) }] }
    score 越高表示语义越相近，一般 score>0.85 可认为高度相关。
    """
    settings = get_settings()
    body = {
        "query": query,
        "use_vector": True,
        "top_k": top_k,
        "lang": lang or settings.server.default_language,
    }
    if status is not None:
        body["status"] = status
    if is_latest is not None:
        body["is_latest"] = is_latest
    return await api_post("/api/v1/standards/search", body)
