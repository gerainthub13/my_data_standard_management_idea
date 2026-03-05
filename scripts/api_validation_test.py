"""
DSMS API 规则校验脚本

覆盖场景：
1. 名称允许括号/点号
2. 分类名称同父节点唯一
3. 非法字符拦截
4. 分类列表 allow_empty_keyword 行为
5. 标准软删除后允许复用 code+version
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

import httpx


def _expect_status(resp: httpx.Response, expected: int, step: str) -> None:
    if resp.status_code != expected:
        raise AssertionError(
            f"[{step}] 期望状态码 {expected}，实际 {resp.status_code}，响应={resp.text}"
        )


def _assert_error_code(resp: httpx.Response, expected_code: str, step: str) -> None:
    body = resp.json()
    actual = body.get("code")
    if actual != expected_code:
        raise AssertionError(f"[{step}] 期望错误码 {expected_code}，实际 {actual}，响应={json.dumps(body, ensure_ascii=False)}")


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    code = f"STD_RULE_{now}"

    created: dict[str, Any] = {}
    with httpx.Client(timeout=timeout_seconds) as client:
        def url(path: str) -> str:
            return f"{base_url}{path}"

        # 0) 健康检查
        resp = client.get(url("/health"))
        _expect_status(resp, 200, "health")

        # 1) 创建两个父分类
        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"父级A-{now}", "category_type": "custom", "scope": "standard"},
        )
        _expect_status(resp, 201, "create_parent_a")
        parent_a = resp.json()
        created["parent_a"] = parent_a["id"]

        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"父级B-{now}", "category_type": "custom", "scope": "standard"},
        )
        _expect_status(resp, 201, "create_parent_b")
        parent_b = resp.json()
        created["parent_b"] = parent_b["id"]

        # 2) 分类名称允许括号和点号
        category_name = "规则.分类(一级)"
        resp = client.post(
            url("/api/v1/categories"),
            json={
                "name": category_name,
                "parent_id": parent_a["id"],
                "category_type": "custom",
                "scope": "standard",
            },
        )
        _expect_status(resp, 201, "create_category_allow_chars")
        category_a = resp.json()
        created["category_a"] = category_a["id"]

        # 3) 同父节点重名应失败
        resp = client.post(
            url("/api/v1/categories"),
            json={
                "name": category_name,
                "parent_id": parent_a["id"],
                "category_type": "custom",
                "scope": "standard",
            },
        )
        _expect_status(resp, 409, "duplicate_same_parent")
        _assert_error_code(resp, "CATEGORY_NAME_CONFLICT", "duplicate_same_parent")

        # 4) 不同父节点允许同名
        resp = client.post(
            url("/api/v1/categories"),
            json={
                "name": category_name,
                "parent_id": parent_b["id"],
                "category_type": "custom",
                "scope": "standard",
            },
        )
        _expect_status(resp, 201, "duplicate_different_parent")
        created["category_b"] = resp.json()["id"]

        # 5) 非法字符拦截（#）
        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"非法#分类{now}", "category_type": "custom", "scope": "standard"},
        )
        _expect_status(resp, 422, "illegal_char_reject")
        _assert_error_code(resp, "REQUEST_VALIDATION_ERROR", "illegal_char_reject")

        # 6) 分类查询：默认不允许空 keyword
        resp = client.get(url("/api/v1/categories"), params={"page": 1, "page_size": 5})
        _expect_status(resp, 400, "list_without_keyword_disallowed")
        _assert_error_code(resp, "CATEGORY_QUERY_INVALID", "list_without_keyword_disallowed")

        # 7) 分类查询：allow_empty_keyword=true 允许
        resp = client.get(
            url("/api/v1/categories"),
            params={"page": 1, "page_size": 5, "allow_empty_keyword": "true"},
        )
        _expect_status(resp, 200, "list_without_keyword_allowed")
        body = resp.json()
        if "items" not in body or "total" not in body:
            raise AssertionError(f"[list_without_keyword_allowed] 返回结构异常：{resp.text}")

        # 8) 标准名称允许括号和点号
        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": code,
                "name": "用户.编号(主键)",
                "description": "用于验证名称规则",
                "category_id": category_a["id"],
            },
        )
        _expect_status(resp, 201, "create_standard_allow_chars")
        standard = resp.json()
        created["standard"] = standard["id"]

        # 9) 软删除后允许复用同 code+version
        resp = client.delete(url(f"/api/v1/standards/{standard['id']}"))
        _expect_status(resp, 204, "delete_standard")

        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": code,
                "name": "用户.编号(主键)",
                "description": "软删除后复用同版本",
                "category_id": category_a["id"],
            },
        )
        _expect_status(resp, 201, "reuse_code_version_after_soft_delete")
        created["recreated_standard"] = resp.json()["id"]

    print(json.dumps({"status": "ok", "case": "api_validation_test", "created": created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "case": "api_validation_test", "error": str(exc)}, ensure_ascii=False))
        raise
