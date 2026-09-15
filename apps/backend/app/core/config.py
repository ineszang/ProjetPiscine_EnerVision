from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
SameSite = Literal["lax", "strict", "none"]

SECRET_KEY_MIN_LENGTH = 32
SENTINELLES_INTERDITES = frozenset(
    {"change_me", "changeme", "secret", "secret-de-test", "changez-moi", "todo"}
)


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

    jwt_issuer: str = "enervision-api"
    jwt_audience: str = "enervision-web"
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_seconds: int = Field(default=604800, ge=3600, le=2592000)

    refresh_cookie_name: str = "ev_refresh"
    cookie_path: str = "/api/v1/auth"
    cookie_samesite: SameSite = "strict"
    cookie_secure: bool | None = None

    argon2_time_cost: int = Field(default=2, ge=1, le=10)
    argon2_memory_cost_kib: int = Field(default=19456, ge=8192)
    argon2_parallelism: int = Field(default=1, ge=1, le=4)
    argon2_max_concurrency: int = Field(default=4, ge=1, le=32)

    login_window_seconds: int = Field(default=900, ge=60)
    login_max_failures_per_identifier_and_ip: int = Field(default=5, ge=1)
    login_max_failures_per_ip: int = Field(default=20, ge=1)
    login_max_failures_per_identifier: int = Field(default=50, ge=1)

    trust_proxy_headers: bool = False
    expose_api_docs: bool | None = None
    metrics_token: SecretStr | None = None

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "prod"

    @property
    def cookies_are_secure(self) -> bool:
        return self.env != "local" if self.cookie_secure is None else self.cookie_secure

    @property
    def api_docs_are_exposed(self) -> bool:
        if self.expose_api_docs is not None:
            return self.expose_api_docs
        return self.env not in ("staging", "prod")

    @model_validator(mode="after")
    def _refuse_les_configurations_dangereuses(self) -> Self:
        secret = self.secret_key.get_secret_value()
        if len(secret) < SECRET_KEY_MIN_LENGTH:
            raise ValueError(
                f"APP_SECRET_KEY doit faire au moins {SECRET_KEY_MIN_LENGTH} caractères"
            )
        if secret.strip().lower() in SENTINELLES_INTERDITES:
            raise ValueError("APP_SECRET_KEY est une valeur d'exemple, il faut en générer une")

        # Piège : `create_app()` passe `debug` à FastAPI, qui renvoie alors la trace complète
        # au client, et à l'engine, qui journalise le SQL et ses paramètres.
        if self.debug and self.env in ("staging", "prod"):
            raise ValueError("APP_DEBUG doit rester faux hors des environnements locaux")

        if "*" in self.cors_origins:
            raise ValueError("APP_CORS_ORIGINS n'accepte pas de joker, les origines sont listées")

        # Sans origines, aucun middleware CORS n'est monté et la vérification d'`Origin` des
        # routes d'authentification n'a plus de référentiel auquel comparer.
        if self.env != "local" and not self.allowed_origins:
            raise ValueError("APP_CORS_ORIGINS doit lister au moins une origine hors local")

        if self.cookie_samesite == "none" and not self.cookies_are_secure:
            raise ValueError("Un cookie SameSite=None est rejeté par les navigateurs sans Secure")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
