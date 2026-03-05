"""
DSMS API 全流程测试脚本

覆盖场景：
1. 分类 + 标准创建
2. i18n 详情读取
3. 更新 + revision + publish + history
4. 关键词/向量搜索
5. 关系创建与重复拦截
6. embedding 重建 accepted/skipped 返回
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any

import httpx


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y"}


def _expect_status(resp: httpx.Response, expected: int, step: str) -> None:
    if resp.status_code != expected:
        raise AssertionError(
            f"[{step}] 期望状态码 {expected}，实际 {resp.status_code}，响应={resp.text}"
        )


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    skip_vector = _env_flag("SKIP_VECTOR")
    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    code = f"STD_FLOW_{now}"

    result: dict[str, Any] = {"code": code}
    with httpx.Client(timeout=timeout_seconds) as client:
        def url(path: str) -> str:
            return f"{base_url}{path}"

        # 0) 健康检查
        resp = client.get(url("/health"))
        _expect_status(resp, 200, "health")

        # 1) 创建分类
        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"流程分类-{now}", "category_type": "custom", "scope": "standard"},
        )
        _expect_status(resp, 201, "create_category")
        category = resp.json()
        result["category_id"] = category["id"]

        # 2) 创建标准
        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": code,
                "name": "订单.编号(唯一)",
                "description": "订单唯一标识",
                "category_id": category["id"],
                "extattributes": {"datatype": "string", "length": 64},
                "translations": [
                    {"fieldname": "name", "language": "en", "content": "Order ID"},
                    {"fieldname": "description", "language": "en", "content": "Unique order identifier"},
                ],
            },
        )
        _expect_status(resp, 201, "create_standard")
        standard = resp.json()
        result["standard_id"] = standard["id"]

        # 3) 读取详情（i18n）
        resp = client.get(url(f"/api/v1/standards/{standard['id']}"), params={"lang": "en"})
        _expect_status(resp, 200, "get_detail_i18n")

        # 4) 更新标准
        resp = client.put(
            url(f"/api/v1/standards/{standard['id']}"),
            json={"description": "订单唯一标识（更新）"},
        )
        _expect_status(resp, 200, "update_standard")

        # 5) 新版本 + 发布
        resp = client.post(url(f"/api/v1/standards/{standard['id']}/revision"))
        _expect_status(resp, 201, "create_revision")
        revision = resp.json()
        result["revision_id"] = revision["id"]

        resp = client.patch(url(f"/api/v1/standards/{revision['id']}/publish"))
        _expect_status(resp, 200, "publish_revision")

        # 6) 历史版本
        resp = client.get(url(f"/api/v1/standards/{code}/history"))
        _expect_status(resp, 200, "history")
        history = resp.json()
        if len(history) < 2:
            raise AssertionError(f"[history] 期望至少 2 个版本，实际 {len(history)}")

        # 7) 关键词搜索
        resp = client.post(url("/api/v1/standards/search"), json={"query": code, "use_vector": False})
        _expect_status(resp, 200, "keyword_search")
        kw_items = resp.json().get("items", [])
        if not kw_items:
            raise AssertionError("[keyword_search] 未返回任何结果")

        # 8) 向量搜索（可选）
        if not skip_vector:
            resp = client.post(url("/api/v1/standards/search"), json={"query": "订单唯一标识", "use_vector": True})
            _expect_status(resp, 200, "vector_search")

        # 9) 创建关系
        relation_payload = {
            "targetid": "external.table.order",
            "targetver": "v1",
            "reltype": "maptotable",
            "targettype": "table",
            "relstatus": 0,
        }
        resp = client.post(url(f"/api/v1/standards/{revision['id']}/relations"), json=relation_payload)
        _expect_status(resp, 201, "create_relation")
        relation = resp.json()
        result["relation_id"] = relation["id"]

        # 10) 重复关系应被拦截
        resp = client.post(url(f"/api/v1/standards/{revision['id']}/relations"), json=relation_payload)
        _expect_status(resp, 409, "duplicate_relation")

        # 11) 查询关系
        resp = client.get(url(f"/api/v1/standards/{revision['id']}/relations"))
        _expect_status(resp, 200, "list_relations")
        rel_items = resp.json()
        if not any(item.get("id") == relation["id"] for item in rel_items):
            raise AssertionError("[list_relations] 未找到刚创建的关系记录")

        # 12) embedding 重建（包含一个不存在 ID）
        fake_id = str(uuid.uuid4())
        resp = client.post(
            url("/api/v1/embeddings/rebuild"),
            json={"refids": [revision["id"], fake_id], "lang": "zh"},
        )
        _expect_status(resp, 202, "embedding_rebuild")
        rebuild = resp.json()
        if rebuild.get("accepted", 0) < 1:
            raise AssertionError(f"[embedding_rebuild] accepted 异常：{resp.text}")
        if rebuild.get("skipped", 0) < 1:
            raise AssertionError(f"[embedding_rebuild] skipped 异常：{resp.text}")
        result["embedding_rebuild"] = rebuild

    print(json.dumps({"status": "ok", "case": "api_workflow_test", "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "case": "api_workflow_test", "error": str(exc)}, ensure_ascii=False))
        raise
