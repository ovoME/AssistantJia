import os
from pathlib import Path
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

def _project_root_for(config_file: Path) -> Path:
    """Resolve the project root in both source-checkout and Docker layouts."""
    backend_dir = Path(config_file).resolve().parent.parent
    return backend_dir.parent if backend_dir.name == "backend" else backend_dir


PROJECT_ROOT = _project_root_for(Path(__file__))

def _resolve_path(v: str) -> str:
    p = Path(v)
    if not p.is_absolute():
        return str((PROJECT_ROOT / p).resolve())
    return str(p.resolve())

class Settings(BaseSettings):
    """小嘉后端配置项，从环境变量或 .env 读取"""
    PROJECT_NAME: str = "AssistantJia Backend"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"

    # LLM 配置 (支持 DeepSeek / 通义千问 / OpenAI 等 OpenAI兼容接口)
    LLM_API_KEY: Optional[str] = Field(default=None, alias="LLM_API_KEY")
    LLM_BASE_URL: str = Field(default="https://api.deepseek.com", alias="LLM_BASE_URL")
    LLM_MODEL: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    LLM_TEMPERATURE: float = 0.3

    # Redis 配置
    REDIS_URL: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Chroma 向量数据库配置
    CHROMA_PERSIST_DIRECTORY: str = Field(default=str(PROJECT_ROOT / "data" / "chroma"), alias="CHROMA_PERSIST_DIRECTORY")
    CHROMA_HOST: Optional[str] = Field(default=None, alias="CHROMA_HOST")
    CHROMA_PORT: int = Field(default=8000, alias="CHROMA_PORT")

    # 图书馆业务系统 (OPAC) 接口
    OPAC_BASE_URL: str = Field(default="http://opac.example.edu.cn", alias="OPAC_BASE_URL")

    DATA_DIRECTORY: str = str(PROJECT_ROOT / "data" / "processed")
    DATA_PROFILE: Literal["local", "integration"] = "local"
    INTEGRATION_DATA_DIRECTORY: str = str(PROJECT_ROOT / "data" / "processed" / "shared-integration-v1")
    CATALOG_DATABASE: str = str(PROJECT_ROOT / "data" / "processed" / "catalog.sqlite3")
    KNOWLEDGE_SOURCE: str = str(PROJECT_ROOT / "data" / "knowledge" / "rules.json")
    USAGE_REPORT: str = str(PROJECT_ROOT / "data" / "processed" / "usage.json")
    DATA_SOURCE_DIRECTORY: str = Field(
        default=str(PROJECT_ROOT / "data" / "raw"), alias="DATA_SOURCE_DIRECTORY"
    )
    OPAC_PROVIDER: Literal["disabled", "demo"] = "disabled"
    ADMIN_TOKEN: Optional[str] = None
    READER_TOKEN_SECRET: Optional[str] = None
    COOKIE_SECURE: bool = False

    @field_validator("DATA_DIRECTORY", "CATALOG_DATABASE", "KNOWLEDGE_SOURCE", "USAGE_REPORT", "CHROMA_PERSIST_DIRECTORY", "DATA_SOURCE_DIRECTORY", mode="before")
    @classmethod
    def resolve_paths(cls, v: str) -> str:
        if v:
            return _resolve_path(v)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
