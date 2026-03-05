"""
config.py — 读取 config.toml 配置，不依赖环境变量。

使用 Python 3.12 内置 tomllib（只读 TOML），配置文件与本模块同目录。
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# config.toml 与本文件在同一目录
_CONFIG_PATH = Path(__file__).parent / "config.toml"


@dataclass(frozen=True)
class ApiConfig:
    base_url: str
    timeout_seconds: int


@dataclass(frozen=True)
class SseConfig:
    host: str
    port: int


@dataclass(frozen=True)
class ServerConfig:
    name: str
    version: str
    default_language: str
    transport: str


@dataclass(frozen=True)
class Settings:
    api: ApiConfig
    server: ServerConfig
    sse: SseConfig


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取并缓存配置，进程内只读取一次。"""
    with open(_CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    api_raw = raw.get("api", {})
    server_raw = raw.get("server", {})
    sse_raw = raw.get("sse", {})

    return Settings(
        api=ApiConfig(
            base_url=api_raw.get("base_url", "http://127.0.0.1:8000"),
            timeout_seconds=int(api_raw.get("timeout_seconds", 30)),
        ),
        server=ServerConfig(
            name=server_raw.get("name", "dsms-mcp-server"),
            version=server_raw.get("version", "0.1.0"),
            default_language=server_raw.get("default_language", "zh"),
            transport=server_raw.get("transport", "sse"),
        ),
        sse=SseConfig(
            host=sse_raw.get("host", "127.0.0.1"),
            port=int(sse_raw.get("port", 9000)),
        ),
    )
