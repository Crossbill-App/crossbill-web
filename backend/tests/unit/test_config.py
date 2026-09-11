"""Tests for Settings configuration validation."""

import pytest

from src.config import Settings


def _build_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
        "REFRESH_TOKEN_SECRET_KEY": "test-refresh-token-secret-key-at-least-32-bytes-long",
        "ADMIN_PASSWORD": "test-admin-password",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


class TestJwtSecretKeyValidation:
    def test_empty_secret_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            _build_settings(SECRET_KEY="")

    def test_short_secret_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            _build_settings(SECRET_KEY="short")

    def test_insecure_example_secret_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            _build_settings(SECRET_KEY="123")

    def test_empty_refresh_secret_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="REFRESH_TOKEN_SECRET_KEY must be set"):
            _build_settings(REFRESH_TOKEN_SECRET_KEY="")

    def test_short_refresh_secret_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="REFRESH_TOKEN_SECRET_KEY must be set"):
            _build_settings(REFRESH_TOKEN_SECRET_KEY="random secret")

    def test_exactly_32_byte_secret_keys_ok(self) -> None:
        access = "a" * 32
        refresh = "b" * 32
        settings = _build_settings(
            SECRET_KEY=access,
            REFRESH_TOKEN_SECRET_KEY=refresh,
        )
        assert len(settings.SECRET_KEY) == 32
        assert len(settings.REFRESH_TOKEN_SECRET_KEY) == 32

    def test_empty_publication_secret_key_ok(self) -> None:
        settings = _build_settings(PUBLICATION_TOKEN_SECRET_KEY="")
        assert settings.PUBLICATION_TOKEN_SECRET_KEY == ""

    def test_short_publication_secret_key_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="PUBLICATION_TOKEN_SECRET_KEY must be at least 32 bytes when set"
        ):
            _build_settings(PUBLICATION_TOKEN_SECRET_KEY="c" * 31)

    def test_exactly_32_byte_publication_secret_key_ok(self) -> None:
        settings = _build_settings(PUBLICATION_TOKEN_SECRET_KEY="c" * 32)
        assert len(settings.PUBLICATION_TOKEN_SECRET_KEY) == 32


class TestCorsOriginsValidation:
    def test_development_empty_origins_ok(self) -> None:
        settings = _build_settings(ENVIRONMENT="development", CORS_ORIGINS=[])
        assert settings.CORS_ORIGINS == []

    def test_development_wildcard_ok(self) -> None:
        settings = _build_settings(ENVIRONMENT="development", CORS_ORIGINS=["*"])
        assert settings.CORS_ORIGINS == ["*"]

    def test_development_default_contains_localhost(self) -> None:
        settings = _build_settings(ENVIRONMENT="development")
        assert "http://localhost:5173" in settings.CORS_ORIGINS
        assert "*" not in settings.CORS_ORIGINS

    def test_production_empty_origins_rejected(self) -> None:
        with pytest.raises(ValueError, match="CORS_ORIGINS must be set"):
            _build_settings(ENVIRONMENT="production", CORS_ORIGINS=[])

    def test_production_wildcard_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not contain wildcard"):
            _build_settings(ENVIRONMENT="production", CORS_ORIGINS=["*"])

    def test_production_wildcard_mixed_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not contain wildcard"):
            _build_settings(
                ENVIRONMENT="production",
                CORS_ORIGINS=["https://example.com", "*"],
            )

    def test_production_explicit_origins_ok(self) -> None:
        settings = _build_settings(
            ENVIRONMENT="production",
            CORS_ORIGINS=["https://example.com"],
            PUBLIC_BASE_URL="https://example.com",
        )
        assert settings.CORS_ORIGINS == ["https://example.com"]


class TestPublicBaseUrlValidation:
    def test_development_empty_ok(self) -> None:
        settings = _build_settings(ENVIRONMENT="development")
        assert settings.PUBLIC_BASE_URL == ""

    def test_production_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="PUBLIC_BASE_URL must be set in production"):
            _build_settings(
                ENVIRONMENT="production",
                CORS_ORIGINS=["https://example.com"],
                PUBLIC_BASE_URL="",
            )

    def test_trailing_slash_stripped(self) -> None:
        settings = _build_settings(PUBLIC_BASE_URL="  https://example.com/  ")
        assert settings.PUBLIC_BASE_URL == "https://example.com"

    def test_scheme_required(self) -> None:
        with pytest.raises(ValueError, match="must start with http"):
            _build_settings(PUBLIC_BASE_URL="example.com")

    def test_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a bare origin"):
            _build_settings(PUBLIC_BASE_URL="https://example.com/api")

    def test_query_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a bare origin"):
            _build_settings(PUBLIC_BASE_URL="https://example.com?a=1")
