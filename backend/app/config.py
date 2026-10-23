import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

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
    CHROMA_PERSIST_DIRECTORY: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIRECTORY")
    CHROMA_HOST: Optional[str] = Field(default=None, alias="CHROMA_HOST")
    CHROMA_PORT: int = Field(default=8000, alias="CHROMA_PORT")

    # 图书馆业务系统 (OPAC) 接口
    OPAC_BASE_URL: str = Field(default="http://opac.example.edu.cn", alias="OPAC_BASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
