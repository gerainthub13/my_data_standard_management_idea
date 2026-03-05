"""
DSMS 只读 UI 相关 API 测试脚本

覆盖场景：
1. 默认只读清单（最新 10 条）返回 has_code_list 字段
2. 关键词只读清单查询
3. 标准详情 + 关联码表详情
4. 码表 bindings 引用查询
5. 搜索接口返回 UI 所需字段（时间、has_code_list）
"""

from __future__ import annotations

import json
import os
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
    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
    skip_vector = _env_flag("SKIP_VECTOR")
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    std_code = f"STD_UI_{now}"
    list_code = f"CL_UI_{now}"

    result: dict[str, Any] = {"standard_code": std_code, "list_code": list_code}

    with httpx.Client(timeout=timeout_seconds) as client:
        def url(path: str) -> str:
            return f"{base_url}{path}"

        # 0) 健康检查
        resp = client.get(url("/health"))
        _expect_status(resp, 200, "health")

        # 1) 创建分类、标准并发布
        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"只读UI分类-{now}", "category_type": "custom", "scope": "standard"},
        )
        _expect_status(resp, 201, "create_category")
        category_id = resp.json()["id"]
        result["category_id"] = category_id

        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": std_code,
                "name": "订单业务类型",
                "description": "用于表示订单所属业务场景",
                "category_id": category_id,
            },
        )
        _expect_status(resp, 201, "create_standard")
        standard_id = resp.json()["id"]
        result["standard_id"] = standard_id

        std_code_2 = f"{std_code}_B"
        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": std_code_2,
                "name": "订单业务类型-扩展",
                "description": "用于测试分页和排序",
                "category_id": category_id,
            },
        )
        _expect_status(resp, 201, "create_standard_2")
        standard_id_2 = resp.json()["id"]
        result["standard_id_2"] = standard_id_2

        std_code_3 = f"{std_code}_DRAFT"
        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": std_code_3,
                "name": "订单业务类型-草稿",
                "description": "用于状态过滤测试",
                "category_id": category_id,
            },
        )
        _expect_status(resp, 201, "create_standard_3_draft")
        standard_id_3 = resp.json()["id"]
        result["standard_id_3"] = standard_id_3

        resp = client.patch(url(f"/api/v1/standards/{standard_id}/publish"))
        _expect_status(resp, 200, "publish_standard")
        resp = client.patch(url(f"/api/v1/standards/{standard_id_2}/publish"))
        _expect_status(resp, 200, "publish_standard_2")

        # 2) 创建并发布码表，然后绑定
        resp = client.post(
            url("/api/v1/code-lists"),
            json={
                "list_code": list_code,
                "name": "订单业务类型码表",
                "purpose": "定义订单业务范围",
                "items": [
                    {"item_code": "ECOM", "item_name": "电商", "meaning": "电商订单", "sort_order": 1},
                    {"item_code": "LOCAL", "item_name": "本地生活", "meaning": "本地生活订单", "sort_order": 2},
                ],
            },
        )
        _expect_status(resp, 201, "create_code_list")
        code_list_id = resp.json()["id"]
        result["code_list_id"] = code_list_id

        resp = client.patch(url(f"/api/v1/code-lists/{code_list_id}/publish"))
        _expect_status(resp, 200, "publish_code_list")

        resp = client.put(
            url(f"/api/v1/standards/{standard_id}/code-list"),
            json={"code_list_id": code_list_id},
        )
        _expect_status(resp, 200, "bind_code_list")

        # 3) 默认只读清单（最新10条）
        resp = client.get(
            url("/api/v1/standards/readonly/list"),
            params={"page": 1, "page_size": 10, "status": 1, "is_latest": "true"},
        )
        _expect_status(resp, 200, "readonly_list_default")
        readonly_items = resp.json().get("items", [])
        hit = next((x for x in readonly_items if x.get("id") == standard_id), None)
        if not hit:
            raise AssertionError("[readonly_list_default] 未找到新建标准")
        if hit.get("has_code_list") is not True:
            raise AssertionError(f"[readonly_list_default] has_code_list 异常：{hit}")

        # 3.0) 状态统计
        resp = client.get(url("/api/v1/standards/readonly/stats"), params={"keyword": std_code})
        _expect_status(resp, 200, "readonly_status_stats")
        stats = resp.json()
        counts = stats.get("counts", {})
        if int(stats.get("total", 0)) < 3:
            raise AssertionError(f"[readonly_status_stats] total 异常：{stats}")
        if int(counts.get("published", 0)) < 2:
            raise AssertionError(f"[readonly_status_stats] published 计数异常：{stats}")
        if int(counts.get("draft", 0)) < 1:
            raise AssertionError(f"[readonly_status_stats] draft 计数异常：{stats}")

        # 3.1) 分页验证
        resp = client.get(
            url("/api/v1/standards/readonly/list"),
            params={"page": 1, "page_size": 1, "order_by": "created_at", "order_dir": "desc"},
        )
        _expect_status(resp, 200, "readonly_page_1")
        page1 = resp.json().get("items", [])
        if len(page1) != 1:
            raise AssertionError("[readonly_page_1] page_size=1 应仅返回1条")

        resp = client.get(
            url("/api/v1/standards/readonly/list"),
            params={"page": 2, "page_size": 1, "order_by": "created_at", "order_dir": "desc"},
        )
        _expect_status(resp, 200, "readonly_page_2")
        page2 = resp.json().get("items", [])
        if len(page2) != 1:
            raise AssertionError("[readonly_page_2] page_size=1 应仅返回1条")
        if page1[0].get("id") == page2[0].get("id"):
            raise AssertionError("[readonly_pagination] 第1页与第2页不应相同")

        # 3.2) 排序验证（code 升序）
        resp = client.get(
            url("/api/v1/standards/readonly/list"),
            params={"page": 1, "page_size": 10, "order_by": "code", "order_dir": "asc", "keyword": std_code},
        )
        _expect_status(resp, 200, "readonly_sort_code_asc")
        sorted_items = resp.json().get("items", [])
        codes = [x.get("code", "") for x in sorted_items]
        if codes != sorted(codes):
            raise AssertionError(f"[readonly_sort_code_asc] 排序异常：{codes}")

        # 4) 关键词只读清单
        resp = client.get(
            url("/api/v1/standards/readonly/list"),
            params={"page": 1, "page_size": 10, "keyword": std_code},
        )
        _expect_status(resp, 200, "readonly_list_keyword")
        keyword_items = resp.json().get("items", [])
        if not any(x.get("id") == standard_id for x in keyword_items):
            raise AssertionError("[readonly_list_keyword] 未命中标准编码关键词")

        # 4.1) 状态过滤（草稿）
        resp = client.get(
            url("/api/v1/standards/readonly/list"),
            params={"page": 1, "page_size": 10, "status": 0, "is_latest": "false", "keyword": std_code},
        )
        _expect_status(resp, 200, "readonly_status_filter_draft")
        draft_items = resp.json().get("items", [])
        if not any(x.get("id") == standard_id_3 for x in draft_items):
            raise AssertionError("[readonly_status_filter_draft] 未命中草稿标准")

        # 5) 标准详情 + 关联码表详情
        resp = client.get(url(f"/api/v1/standards/{standard_id}"), params={"lang": "zh"})
        _expect_status(resp, 200, "standard_detail")
        detail = resp.json()
        if not detail.get("code_list") or detail["code_list"].get("id") != code_list_id:
            raise AssertionError(f"[standard_detail] 未返回正确 code_list 摘要：{detail}")

        resp = client.get(url(f"/api/v1/code-lists/{code_list_id}"), params={"include_items": "true"})
        _expect_status(resp, 200, "code_list_detail")
        code_list_detail = resp.json()
        if len(code_list_detail.get("items", [])) < 2:
            raise AssertionError("[code_list_detail] 码表子项数量异常")

        # 6) bindings 引用清单
        resp = client.get(url(f"/api/v1/code-lists/{code_list_id}/bindings"))
        _expect_status(resp, 200, "code_list_bindings")
        binding_items = resp.json().get("items", [])
        if not any(x.get("id") == standard_id for x in binding_items):
            raise AssertionError("[code_list_bindings] 未找到绑定标准")

        # 7) 搜索接口字段完整性（关键词）
        resp = client.post(
            url("/api/v1/standards/search"),
            json={"query": std_code, "use_vector": False, "top_k": 10},
        )
        _expect_status(resp, 200, "search_keyword")
        search_items = resp.json().get("items", [])
        if not search_items:
            raise AssertionError("[search_keyword] 未返回结果")
        target = next((x for x in search_items if x.get("id") == standard_id), None)
        if not target:
            raise AssertionError("[search_keyword] 未包含目标标准")
        required = ("created_at", "updated_at", "has_code_list")
        for field in required:
            if field not in target:
                raise AssertionError(f"[search_keyword] 缺少字段 {field}")

        # 8) 向量搜索（可选）
        if not skip_vector:
            resp = client.post(
                url("/api/v1/standards/search"),
                json={
                    "query": "订单业务场景",
                    "use_vector": True,
                    "top_k": 10,
                    "lang": "zh",
                    "status": 1,
                    "is_latest": True,
                },
            )
            _expect_status(resp, 200, "search_vector")
            vec_items = resp.json().get("items", [])
            if any(int(item.get("status", -1)) != 1 for item in vec_items):
                raise AssertionError(f"[search_vector] 返回了非已发布状态结果：{vec_items}")

    print(json.dumps({"status": "ok", "case": "api_readonly_ui_test", "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "case": "api_readonly_ui_test", "error": str(exc)}, ensure_ascii=False))
        raise
