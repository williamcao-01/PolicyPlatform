from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


Environment = Literal["local", "test", "staging", "production"]


def _getenv(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in {None, ""} else default


def _getbool(name: str, default: bool = False) -> bool:
    value = _getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _getint(name: str, default: int) -> int:
    value = _getenv(name)
    return int(value) if value is not None else default


def _getfloat(name: str, default: float) -> float:
    value = _getenv(name)
    return float(value) if value is not None else default


def _getlist(name: str) -> list[str]:
    value = _getenv(name)
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class DatabaseSettings(BaseModel):
    """Database connection settings for the production SQLAlchemy stack."""

    url: str = Field(
        "postgresql+psycopg://policy_assistant:policy_assistant@localhost:5432/policy_assistant",
    )
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_pre_ping: bool = True


class ObjectStorageSettings(BaseModel):
    """Object storage settings. Provider-specific clients should read only their own fields."""

    provider: str = "memory"
    bucket: str = "policy-assistant"
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: SecretStr | None = None
    local_root: Path | None = None


class QueueSettings(BaseModel):
    """Async job queue settings with an in-memory default for local development."""

    provider: str = "memory"
    url: str | None = None
    default_topic: str = "policy-assistant.jobs"
    dead_letter_topic: str = "policy-assistant.dead-letter"


class LLMSettings(BaseModel):
    """Provider-neutral LLM configuration."""

    provider: str = "disabled"
    model: str | None = None
    api_key: SecretStr | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2


class AuthSettings(BaseModel):
    """Local auth settings used until an enterprise SSO adapter is connected."""

    token_secret: SecretStr = Field(SecretStr("local-development-change-me"))
    access_token_seconds: int = 3600
    refresh_token_seconds: int = 604800
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: SecretStr = Field(SecretStr("admin123"))
    enforce_legacy_rbac: bool = False


class Settings(BaseModel):
    """Application settings for the productionized backend modules."""

    app_name: str = "policy-assistant"
    environment: Environment = "local"
    debug: bool = False
    api_prefix: str = "/api"
    allowed_origins: list[str] = Field(default_factory=list)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    object_storage: ObjectStorageSettings = Field(default_factory=ObjectStorageSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=_getenv("APP_NAME", "policy-assistant") or "policy-assistant",
        environment=(_getenv("ENVIRONMENT", "local") or "local"),  # type: ignore[arg-type]
        debug=_getbool("DEBUG", False),
        api_prefix=_getenv("API_PREFIX", "/api") or "/api",
        allowed_origins=_getlist("ALLOWED_ORIGINS"),
        database=DatabaseSettings(
            url=_getenv(
                "DATABASE_URL",
                _getenv(
                    "DATABASE_DSN",
                    "postgresql+psycopg://policy_assistant:policy_assistant@localhost:5432/policy_assistant",
                ),
            )
            or "postgresql+psycopg://policy_assistant:policy_assistant@localhost:5432/policy_assistant",
            echo=_getbool("DATABASE_ECHO", False),
            pool_size=_getint("DATABASE_POOL_SIZE", 5),
            max_overflow=_getint("DATABASE_MAX_OVERFLOW", 10),
            pool_pre_ping=_getbool("DATABASE_POOL_PRE_PING", True),
        ),
        object_storage=ObjectStorageSettings(
            provider=_getenv("OBJECT_STORAGE_PROVIDER", "memory") or "memory",
            bucket=_getenv("OBJECT_STORAGE_BUCKET", "policy-assistant") or "policy-assistant",
            endpoint_url=_getenv("OBJECT_STORAGE_ENDPOINT_URL"),
            access_key_id=_getenv("OBJECT_STORAGE_ACCESS_KEY_ID"),
            secret_access_key=_getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY"),
            local_root=Path(value) if (value := _getenv("OBJECT_STORAGE_LOCAL_ROOT")) else None,
        ),
        queue=QueueSettings(
            provider=_getenv("QUEUE_PROVIDER", "memory") or "memory",
            url=_getenv("QUEUE_URL"),
            default_topic=_getenv("QUEUE_DEFAULT_TOPIC", "policy-assistant.jobs") or "policy-assistant.jobs",
            dead_letter_topic=_getenv("QUEUE_DEAD_LETTER_TOPIC", "policy-assistant.dead-letter")
            or "policy-assistant.dead-letter",
        ),
        llm=LLMSettings(
            provider=_getenv("LLM_PROVIDER", "disabled") or "disabled",
            model=_getenv("LLM_MODEL"),
            api_key=_getenv("LLM_API_KEY"),
            base_url=_getenv("LLM_BASE_URL"),
            timeout_seconds=_getfloat("LLM_TIMEOUT_SECONDS", 60.0),
            max_retries=_getint("LLM_MAX_RETRIES", 2),
        ),
        auth=AuthSettings(
            token_secret=_getenv("AUTH_TOKEN_SECRET", "local-development-change-me") or "local-development-change-me",
            access_token_seconds=_getint("AUTH_ACCESS_TOKEN_SECONDS", 3600),
            refresh_token_seconds=_getint("AUTH_REFRESH_TOKEN_SECONDS", 604800),
            bootstrap_admin_username=_getenv("BOOTSTRAP_ADMIN_USERNAME", "admin") or "admin",
            bootstrap_admin_password=_getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123") or "admin123",
            enforce_legacy_rbac=_getbool("AUTH_ENFORCE_LEGACY_RBAC", False),
        ),
    )
