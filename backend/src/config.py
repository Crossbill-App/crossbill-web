"""Application configuration."""

import logging
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path constants - calculated once at module load
BACKEND_ROOT = Path(__file__).parent.parent.resolve()
BOOK_FILES_DIR = BACKEND_ROOT / "book-files"
BOOK_COVERS_DIR = BOOK_FILES_DIR / "book-covers"
EPUBS_DIR = BOOK_FILES_DIR / "epubs"
PDFS_DIR = BOOK_FILES_DIR / "pdfs"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql://crossbill:crossbill_dev_password@localhost:5432/crossbill"

    SECRET_KEY: str = ""

    # API (constants, not from env)
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "crossbill API"
    VERSION: str = "0.1.0"

    # Environment
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # Rate limiting (per-IP, applied app-wide via slowapi)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "300/minute"

    # Number of reverse proxies in front of the app that append to
    # X-Forwarded-For. 0 means the app is directly exposed and the header is
    # ignored entirely; anything else would let callers pick their own
    # rate-limit bucket. Set to 1 behind a single edge proxy (Railway,
    # Cloudflare, nginx), 2 behind two chained proxies, and so on.
    TRUSTED_PROXY_HOPS: int = 0

    # Admin setup (for first-time initialization on a fresh deployment)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_SECRET_KEY: str = ""
    COOKIE_SECURE: bool = True
    PASSWORD_PEPPER: str = ""

    # How many Argon2id hashes may run concurrently. Each costs ~64 MiB, so this
    # is the ceiling on memory an unauthenticated flood of logins can pin down.
    # Raise it only if the host has memory and cores to spare.
    PASSWORD_HASH_CONCURRENCY: int = 2

    # Registration
    ALLOW_USER_REGISTRATIONS: bool = True

    # Reading sessions
    MINIMUM_READING_SESSION_DURATION: int = 120

    # AI configuration
    AI_PROVIDER: (
        Literal["ollama"]
        | Literal["openai"]
        | Literal["anthropic"]
        | Literal["google"]
        | Literal["openrouter"]
        | None
    ) = None
    AI_MODEL_NAME: str | None = None

    # ollama
    OPENAI_BASE_URL: str | None = None
    # openai
    OPENAI_API_KEY: str | None = None
    # anthropic
    ANTHROPIC_API_KEY: str | None = None
    # google
    GEMINI_API_KEY: str | None = None
    # openrouter
    OPENROUTER_API_KEY: str | None = None

    # Worker
    EMBEDDED_WORKER: bool = True
    WORKER_CONCURRENCY: int = 2

    # S3-compatible storage (optional — if set, files are stored in S3 instead of local disk)
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str = "us-east-1"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ai_enabled(self) -> bool:
        """Whether AI features are enabled."""
        return self.AI_PROVIDER is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def s3_enabled(self) -> bool:
        """Whether S3 storage is enabled."""
        return (
            self.S3_ENDPOINT_URL is not None
            and self.S3_ACCESS_KEY_ID is not None
            and self.S3_SECRET_ACCESS_KEY is not None
            and self.S3_BUCKET_NAME is not None
        )

    @field_validator("ADMIN_PASSWORD", mode="after")
    @classmethod
    def strip_admin_password(cls, value: str) -> str:
        """Strip whitespace from admin password."""
        return value.strip()

    @field_validator("TRUSTED_PROXY_HOPS", mode="after")
    @classmethod
    def validate_trusted_proxy_hops(cls, value: int) -> int:
        """Reject a negative proxy-hop count, which would index the wrong entry."""
        if value < 0:
            msg = "TRUSTED_PROXY_HOPS must be 0 or greater"
            raise ValueError(msg)
        return value

    @field_validator("PASSWORD_HASH_CONCURRENCY", mode="after")
    @classmethod
    def validate_password_hash_concurrency(cls, value: int) -> int:
        """Require at least one hashing slot, or no login could ever complete."""
        if value < 1:
            msg = "PASSWORD_HASH_CONCURRENCY must be at least 1"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_jwt_secret_keys(self) -> "Settings":
        """Require JWT signing secrets to be set and long enough to resist brute force."""
        minimum_length = 32
        for field_name in ("SECRET_KEY", "REFRESH_TOKEN_SECRET_KEY"):
            value: str = getattr(self, field_name)
            if len(value.encode("utf-8")) < minimum_length:
                msg = (
                    f"{field_name} must be set to at least {minimum_length} bytes. "
                    "Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_admin_password(self) -> "Settings":
        """Require ADMIN_PASSWORD to be set to a non-default value for first-run provisioning."""
        if not self.ADMIN_PASSWORD:
            msg = (
                "ADMIN_PASSWORD must be set (e.g. in your .env file) so the initial "
                "admin user can be provisioned on first startup."
            )
            raise ValueError(msg)
        if self.ADMIN_PASSWORD.lower() == "admin":
            msg = (
                "ADMIN_PASSWORD must not be set to the insecure default 'admin'. "
                "Choose a strong password — you can change it again from the UI after first login."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_cors_origins_in_production(self) -> "Settings":
        """Reject wildcard or empty CORS origins in production."""
        if self.ENVIRONMENT != "production":
            return self
        if not self.CORS_ORIGINS:
            msg = "CORS_ORIGINS must be set to explicit origins in production"
            raise ValueError(msg)
        if "*" in self.CORS_ORIGINS:
            msg = "CORS_ORIGINS must not contain wildcard '*' in production"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_ai_provider_config(self) -> "Settings":
        """Validate AI provider configuration."""
        if self.AI_PROVIDER is not None and self.AI_MODEL_NAME is None:
            msg = "AI_MODEL_NAME is required when AI_PROVIDER is 'openai'"
            raise ValueError(msg)

        if self.AI_PROVIDER == "ollama" and not self.OPENAI_BASE_URL:
            msg = "OPENAI_BASE_URL is required when AI_PROVIDER is 'ollama'"
            raise ValueError(msg)
        if self.AI_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            msg = "OPENAI_API_KEY is required when AI_PROVIDER is 'openai'"
            raise ValueError(msg)
        if self.AI_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            msg = "ANTHROPIC_API_KEY is required when AI_PROVIDER is 'anthropic'"
            raise ValueError(msg)
        if self.AI_PROVIDER == "google" and not self.GEMINI_API_KEY:
            msg = "GEMINI_API_KEY is required when AI_PROVIDER is 'google'"
            raise ValueError(msg)
        if self.AI_PROVIDER == "openrouter" and not self.OPENROUTER_API_KEY:
            msg = "OPENROUTER_API_KEY is required when AI_PROVIDER is 'openrouter'"
            raise ValueError(msg)
        return self


def configure_logging(environment: str = "development") -> None:
    """Configure structured logging with structlog."""
    # Determine if we should use JSON output (production) or console output (dev)
    use_json = environment == "production"

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if environment == "development" else logging.INFO,
    )

    # Configure structlog
    processors: list[Callable[..., Any]] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if use_json:
        # Production: JSON output
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Console output with colors
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
