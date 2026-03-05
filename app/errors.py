from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ApiError(Exception):
    """
    统一业务异常对象，用于构建商业系统常见的错误返回结构。
    """

    status_code: int
    code: str
    message: str
    errors: list[dict[str, Any]]
    warnings: list[str]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    errors: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> ApiError:
    return ApiError(
        status_code=status_code,
        code=code,
        message=message,
        errors=errors or [],
        warnings=warnings or [],
    )
