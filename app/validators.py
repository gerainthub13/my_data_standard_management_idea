from __future__ import annotations

import re


# 展示名称（分类名称、数据标准名称）允许：
# 1) 以中文或英文字母开头
# 2) 后续可包含中文、英文、数字、空格、中划线（-）、括号（()（））、点号（.）
_DISPLAY_NAME_PATTERN = re.compile(r"^[A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff \-\(\)\.（）]{0,199}$")
_DISPLAY_NAME_ILLEGAL_PATTERN = re.compile(r"[^A-Za-z0-9\u4e00-\u9fff \-\(\)\.（）]")

# 标准编码约束：英文字母开头，允许字母、数字、中划线、下划线
_STANDARD_CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,49}$")


def ensure_valid_display_name(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    if normalized[0].isdigit():
        raise ValueError(f"{field_name}不能以数字开头")

    illegal_chars = sorted(set(_DISPLAY_NAME_ILLEGAL_PATTERN.findall(normalized)))
    if illegal_chars:
        joined = " ".join(illegal_chars)
        raise ValueError(f"{field_name}包含非法字符：{joined}")

    if not _DISPLAY_NAME_PATTERN.match(normalized):
        raise ValueError(f"{field_name}仅支持中文、英文、数字、空格、中划线(-)、括号和点号(.)")
    return normalized


def ensure_valid_standard_code(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("标准编码不能为空")
    if not _STANDARD_CODE_PATTERN.match(normalized):
        raise ValueError("标准编码仅支持英文字母开头，且只允许字母、数字、中划线和下划线")
    return normalized


def normalize_language(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("language 不能为空")
    if len(normalized) > 10:
        raise ValueError("language 长度不能超过 10")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", normalized):
        raise ValueError("language 仅支持小写字母、数字和中划线")
    return normalized
