from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # 读取 .env 中的配置
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 应用基础信息
    app_name: str = "DSMS"
    environment: str = "dev"

    # 数据库连接配置（异步 SQLAlchemy）
    database_url: str = Field(
        default="postgresql+asyncpg://vector:vector@127.0.0.1:5432/vector",
        validation_alias="DATABASE_URL",
        description="Async SQLAlchemy database URL",
    )

    # LM Studio Embedding 服务配置
    lmstudio_base_url: str = Field(default="http://127.0.0.1:1234", validation_alias="LMSTUDIO_BASE_URL")
    lmstudio_embedding_model: str = Field(
        # default="text-embedding-qwen3-embedding-0.6b",
        default="text-embedding-bge-large-zh-v1.5",
        validation_alias="LMSTUDIO_EMBEDDING_MODEL",
    )
    lmstudio_timeout_seconds: int = Field(default=30, validation_alias="LMSTUDIO_TIMEOUT_SECONDS")

    # 默认语言
    default_language: str = Field(default="zh", validation_alias="DEFAULT_LANGUAGE")


@lru_cache
def get_settings() -> Settings:
    # 通过缓存避免重复读取配置
    return Settings()
