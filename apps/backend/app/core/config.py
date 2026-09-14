from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "EnerVision API"
    version: str = "0.1.0"
    env: Environment = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    secret_key: SecretStr
    cors_origins: str = ""
    database_url: str = Field(validation_alias="DATABASE_URL")
    database_pool_size: int = 5
    database_max_overflow: int = 10

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
