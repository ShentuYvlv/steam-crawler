from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Steam Review Admin"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api"

    database_url: str = Field(
        default="postgresql+asyncpg://steam:steam@localhost:5432/steam_reviews",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )

    jwt_secret_key: str = Field(default="change-me", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    aliyun_api_key: str | None = Field(default=None, validation_alias="ALIYUN_API_KEY")
    aliyun_model: str = Field(default="qwen-plus", validation_alias="ALIYUN_MODEL")

    steam_cookie_file: str = Field(
        default="./data/steam_cookie.txt",
        validation_alias="STEAM_COOKIE_FILE",
    )
    task_scheduler_enabled: bool = Field(default=True, validation_alias="TASK_SCHEDULER_ENABLED")
    task_scheduler_poll_seconds: int = Field(
        default=60,
        validation_alias="TASK_SCHEDULER_POLL_SECONDS",
    )

    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            item.strip()
            for item in self.cors_origins_raw.split(",")
            if item.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
