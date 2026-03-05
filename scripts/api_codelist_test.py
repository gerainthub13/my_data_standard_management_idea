"""
DSMS 码表能力测试脚本

覆盖场景：
1. 码表创建（含子项）
2. 码表关键词搜索（主表+子项）
3. 码表发布 + 标准绑定
4. revision + 子项批量替换 + 历史查询
5. 被已发布标准引用时删除拦截
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx


def _expect_status(resp: httpx.Response, expected: int, step: str) -> None:
    if resp.status_code != expected:
        raise AssertionError(
            f"[{step}] 期望状态码 {expected}，实际 {resp.status_code}，响应={resp.text}"
        )


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    std_code = f"STD_CL_{now}"
    list_code = f"CL_{now}"

    result: dict[str, Any] = {
        "standard_code": std_code,
        "list_code": list_code,
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        def url(path: str) -> str:
            return f"{base_url}{path}"

        resp = client.get(url("/health"))
        _expect_status(resp, 200, "health")

        # 1) 创建分类
        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"码表测试分类-{now}", "category_type": "custom", "scope": "standard"},
        )
        _expect_status(resp, 201, "create_category")
        category_id = resp.json()["id"]
        result["category_id"] = category_id

        # 2) 创建并发布数据标准（用于绑定测试）
        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": std_code,
                "name": "订单状态",
                "description": "订单状态字段",
                "category_id": category_id,
            },
        )
        _expect_status(resp, 201, "create_standard")
        standard_id = resp.json()["id"]
        result["standard_id"] = standard_id

        resp = client.patch(url(f"/api/v1/standards/{standard_id}/publish"))
        _expect_status(resp, 200, "publish_standard")

        # 3) 创建码表（含子项）
        resp = client.post(
            url("/api/v1/code-lists"),
            json={
                "list_code": list_code,
                "name": "订单状态码表",
                "purpose": "描述订单生命周期状态",
                "items": [
                    {"item_code": "CREATED", "item_name": "已创建", "meaning": "订单新建", "sort_order": 1},
                    {"item_code": "PAID", "item_name": "已支付", "meaning": "用户完成支付", "sort_order": 2},
                ],
            },
        )
        _expect_status(resp, 201, "create_code_list")
        code_list = resp.json()
        code_list_id = code_list["id"]
        result["code_list_id"] = code_list_id

        # 4) 关键词搜索（命中主表编码）
        resp = client.post(
            url("/api/v1/code-lists/search"),
            json={"query": list_code, "top_k": 10, "only_bindable": False},
        )
        _expect_status(resp, 200, "search_code_list_by_list")
        by_list = resp.json().get("items", [])
        if not by_list:
            raise AssertionError("[search_code_list_by_list] 未返回结果")

        # 5) 关键词搜索（命中子项）
        resp = client.post(
            url("/api/v1/code-lists/search"),
            json={"query": "支付", "top_k": 10, "only_bindable": False},
        )
        _expect_status(resp, 200, "search_code_list_by_item")
        by_item = resp.json().get("items", [])
        if not any(item.get("id") == code_list_id for item in by_item):
            raise AssertionError("[search_code_list_by_item] 未命中码表子项关键词")

        # 6) 发布码表
        resp = client.patch(url(f"/api/v1/code-lists/{code_list_id}/publish"))
        _expect_status(resp, 200, "publish_code_list")

        # 7) 绑定标准与码表
        resp = client.put(
            url(f"/api/v1/standards/{standard_id}/code-list"),
            json={"code_list_id": code_list_id},
        )
        _expect_status(resp, 200, "bind_code_list")
        binding = resp.json()
        if binding.get("code_list_id") != code_list_id:
            raise AssertionError(f"[bind_code_list] 绑定结果异常：{binding}")

        # 7.1) 标准详情应返回绑定码表摘要
        resp = client.get(url(f"/api/v1/standards/{standard_id}"), params={"lang": "zh"})
        _expect_status(resp, 200, "standard_detail_with_code_list")
        detail = resp.json()
        if not detail.get("code_list") or detail["code_list"].get("id") != code_list_id:
            raise AssertionError(f"[standard_detail_with_code_list] 详情未返回正确码表摘要：{detail}")

        # 7.2) 码表绑定清单应包含该标准
        resp = client.get(url(f"/api/v1/code-lists/{code_list_id}/bindings"))
        _expect_status(resp, 200, "code_list_bindings")
        bindings = resp.json().get("items", [])
        if not any(item.get("id") == standard_id for item in bindings):
            raise AssertionError("[code_list_bindings] 未找到刚绑定的标准")

        # 8) 删除应被拦截（已发布标准在引用）
        resp = client.delete(url(f"/api/v1/code-lists/{code_list_id}"))
        _expect_status(resp, 409, "delete_code_list_in_use")

        # 9) 创建 revision
        resp = client.post(url(f"/api/v1/code-lists/{code_list_id}/revision"))
        _expect_status(resp, 201, "create_code_list_revision")
        revision = resp.json()
        revision_id = revision["id"]
        result["revision_id"] = revision_id

        # 10) 批量替换 revision 子项
        resp = client.put(
            url(f"/api/v1/code-lists/{revision_id}/items"),
            json={
                "items": [
                    {"item_code": "CREATED", "item_name": "已创建", "meaning": "订单新建", "sort_order": 1},
                    {"item_code": "CLOSED", "item_name": "已关闭", "meaning": "订单关闭", "sort_order": 3},
                ]
            },
        )
        _expect_status(resp, 200, "replace_revision_items")
        items = resp.json().get("items", [])
        if not any(item.get("item_code") == "CLOSED" for item in items):
            raise AssertionError("[replace_revision_items] 子项更新未生效")

        # 11) 历史查询
        resp = client.get(url(f"/api/v1/code-lists/code/{list_code}/history"))
        _expect_status(resp, 200, "code_list_history")
        history = resp.json()
        if len(history) < 2:
            raise AssertionError(f"[code_list_history] 期望至少2个版本，实际={len(history)}")

        # 12) 解绑后删除旧版码表
        resp = client.put(
            url(f"/api/v1/standards/{standard_id}/code-list"),
            json={"code_list_id": None},
        )
        _expect_status(resp, 200, "unbind_code_list")

        resp = client.delete(url(f"/api/v1/code-lists/{code_list_id}"))
        _expect_status(resp, 204, "delete_code_list_after_unbind")

    print(json.dumps({"status": "ok", "case": "api_codelist_test", "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "case": "api_codelist_test", "error": str(exc)}, ensure_ascii=False))
        raise
