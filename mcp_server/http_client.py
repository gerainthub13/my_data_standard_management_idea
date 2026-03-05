"""
http_client.py — 对 DSMS API 发起 HTTP 请求的异步封装。

所有 MCP 工具通过本模块调用后端 API，统一处理超时、错误响应和连接异常。
错误信息会以人类可读文本返回，方便 LLM 理解并决策下一步操作。
"""
from __future__ import annotations

from typing import Any

import httpx

from mcp_server.config import get_settings


def _base_url() -> str:
    return get_settings().api.base_url.rstrip("/")


def _timeout() -> float:
    return float(get_settings().api.timeout_seconds)


def _format_error(resp: httpx.Response) -> str:
    """将非 2xx 响应格式化为 LLM 可读的错误字符串。"""
    try:
        body = resp.json()
        # DSMS API 错误结构：{ detail: { code, message, errors, warnings } }
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            code = detail.get("code", "UNKNOWN")
            message = detail.get("message", str(detail))
            errors = detail.get("errors", [])
            warnings = detail.get("warnings", [])
            parts = [f"[{code}] {message}"]
            for e in errors:
                if isinstance(e, dict):
                    parts.append(f"  - {e.get('field', '')}: {e.get('message', e)}")
            for w in warnings:
                parts.append(f"  ⚠ {w}")
            return "\n".join(parts)
        return str(detail)
    except Exception:
        return f"HTTP {resp.status_code}: {resp.text[:500]}"


async def api_get(path: str, params: dict[str, Any] | None = None) -> dict | list | str:
    """执行 GET 请求，返回响应 JSON 或错误描述字符串。"""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.get(url, params=_clean_params(params))
        if resp.is_success:
            return resp.json()
        return _format_error(resp)
    except httpx.TimeoutException:
        return f"请求超时（>{_timeout()}s）：GET {path}"
    except httpx.ConnectError:
        return f"无法连接到 DSMS API（{_base_url()}），请确认服务已启动。"


async def api_post(path: str, json: dict[str, Any] | None = None) -> dict | list | str:
    """执行 POST 请求，返回响应 JSON 或错误描述字符串。"""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.post(url, json=json or {})
        if resp.is_success:
            # 204 No Content
            if resp.status_code == 204:
                return {"ok": True}
            return resp.json()
        return _format_error(resp)
    except httpx.TimeoutException:
        return f"请求超时（>{_timeout()}s）：POST {path}"
    except httpx.ConnectError:
        return f"无法连接到 DSMS API（{_base_url()}），请确认服务已启动。"


async def api_put(path: str, json: dict[str, Any] | None = None) -> dict | list | str:
    """执行 PUT 请求，返回响应 JSON 或错误描述字符串。"""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.put(url, json=json or {})
        if resp.is_success:
            if resp.status_code == 204:
                return {"ok": True}
            return resp.json()
        return _format_error(resp)
    except httpx.TimeoutException:
        return f"请求超时（>{_timeout()}s）：PUT {path}"
    except httpx.ConnectError:
        return f"无法连接到 DSMS API（{_base_url()}），请确认服务已启动。"


async def api_patch(path: str, json: dict[str, Any] | None = None) -> dict | list | str:
    """执行 PATCH 请求，返回响应 JSON 或错误描述字符串。"""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.patch(url, json=json or {})
        if resp.is_success:
            if resp.status_code == 204:
                return {"ok": True}
            return resp.json()
        return _format_error(resp)
    except httpx.TimeoutException:
        return f"请求超时（>{_timeout()}s）：PATCH {path}"
    except httpx.ConnectError:
        return f"无法连接到 DSMS API（{_base_url()}），请确认服务已启动。"


async def api_delete(path: str) -> dict | str:
    """执行 DELETE 请求，返回 {"ok": True} 或错误描述字符串。"""
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.delete(url)
        if resp.is_success:
            return {"ok": True}
        return _format_error(resp)
    except httpx.TimeoutException:
        return f"请求超时（>{_timeout()}s）：DELETE {path}"
    except httpx.ConnectError:
        return f"无法连接到 DSMS API（{_base_url()}），请确认服务已启动。"


def _clean_params(params: dict | None) -> dict:
    """过滤 None 值，避免将 null 传给 API 查询参数。"""
    if not params:
        return {}
    return {k: v for k, v in params.items() if v is not None}
