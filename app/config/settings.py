# app/config/settings.py

# from pydantic_settings import BaseSettings
#
#
# class Settings(BaseSettings):
#     LLM_API_KEY: str = ""
#     LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
#     LLM_MODEL: str = "qwen3.6-plus"
#     LLM_TIMEOUT: int = 60
#
#     # RAG 模块使用的 DashScope Key
#     dashscope_api_key: str = ""
#
#     # 新增这两个
#     LLM_ENABLE_THINKING: bool = True
#     LLM_STREAM: bool = True
#
#     class Config:
#         env_file = ".env"
#         env_file_encoding = "utf-8"
#
#
# settings = Settings()



# app/config/settings.py

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "chronic-care-agent"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    database_url: str = "sqlite:///data/sqlite/chronic_care_v2.db"

    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=720, ge=5, le=43200)

    redis_url: str = ""
    cors_origins: str = "*"
    allow_dev_login: bool = True

    wx_appid: str = ""
    wx_secret: str = ""

    intent_base_url: str = "http://127.0.0.1:8020"
    intent_api_key: str = ""
    intent_timeout: float = Field(default=60.0, ge=1, le=180)

    rag_base_url: str = "http://127.0.0.1:8010"
    rag_api_key: str = ""
    rag_timeout: float = Field(default=45.0, ge=1, le=180)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_fail_open: bool = True

    # 主项目 LLM 配置
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.6-plus"
    llm_timeout: int = 60
    llm_enable_thinking: bool = True
    llm_stream: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env == "prod":
            if self.jwt_secret_key == "dev-only-change-me" or len(self.jwt_secret_key) < 32:
                raise ValueError("生产环境必须配置长度不少于 32 的 JWT_SECRET_KEY")
            if not self.redis_url:
                raise ValueError("生产环境必须配置 REDIS_URL")
            if self.allow_dev_login:
                raise ValueError("生产环境必须关闭 ALLOW_DEV_LOGIN")
        return self


settings = Settings()
