from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import ApiError


def _build_payload(
    *,
    code: str,
    message: str,
    errors: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "code": code,
        "message": message,
        "errors": errors or [],
        "warnings": warnings or [],
    }


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_payload(
            code=exc.code,
            message=exc.message,
            errors=exc.errors,
            warnings=exc.warnings,
        ),
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    normalized_errors: list[dict[str, Any]] = []
    for item in exc.errors():
        loc = [str(part) for part in item.get("loc", [])]
        # loc 示例：("body", "name") / ("query", "page")
        field = ".".join(loc[1:]) if len(loc) > 1 else ".".join(loc) or "unknown"
        normalized_errors.append(
            {
                "field": field,
                "message": item.get("msg", "参数校验失败"),
                "type": item.get("type", "validation_error"),
            }
        )

    return JSONResponse(
        status_code=422,
        content=_build_payload(
            code="REQUEST_VALIDATION_ERROR",
            message="请求参数校验失败",
            errors=normalized_errors,
            warnings=["请根据 errors 字段修正请求参数后重试。"],
        ),
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        payload = {
            "success": False,
            "code": exc.detail.get("code", "HTTP_ERROR"),
            "message": exc.detail.get("message", "请求处理失败"),
            "errors": exc.detail.get("errors", []),
            "warnings": exc.detail.get("warnings", []),
        }
    else:
        payload = _build_payload(
            code="HTTP_ERROR",
            message=str(exc.detail),
            errors=[],
            warnings=[],
        )

    return JSONResponse(status_code=exc.status_code, content=payload)


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_build_payload(
            code="INTERNAL_SERVER_ERROR",
            message="服务内部错误，请联系管理员",
            errors=[{"field": "server", "message": str(exc)}],
            warnings=["如问题持续出现，请附带请求参数与时间联系技术支持。"],
        ),
    )
