"""Tests for database URL scheme handling.

Hosted providers hand out `postgres://` URLs that SQLAlchemy refuses to load, which
takes down the whole process at startup. These cover both paths that build an engine
URL: application settings and Alembic's own environment read.
"""

import pytest
from sqlalchemy.engine.url import make_url

from src.config import Settings, normalize_database_url
from src.database import make_async_url


class TestNormalizeDatabaseUrl:
    def test_legacy_postgres_scheme_is_rewritten(self) -> None:
        assert (
            normalize_database_url("postgres://user:pw@host:5432/db")
            == "postgresql://user:pw@host:5432/db"
        )

    def test_canonical_postgresql_scheme_is_untouched(self) -> None:
        url = "postgresql://user:pw@host:5432/db"
        assert normalize_database_url(url) == url

    def test_sqlite_url_is_untouched(self) -> None:
        url = "sqlite+aiosqlite:///:memory:"
        assert normalize_database_url(url) == url

    def test_driver_qualified_postgres_url_is_untouched(self) -> None:
        url = "postgresql+psycopg://user:pw@host:5432/db"
        assert normalize_database_url(url) == url

    def test_only_the_scheme_is_rewritten(self) -> None:
        """A password or query value may itself contain the legacy prefix."""
        normalized = normalize_database_url("postgres://user:postgres://@host:5432/db")
        assert normalized == "postgresql://user:postgres://@host:5432/db"


class TestSettingsNormalizeDatabaseUrl:
    def test_settings_normalizes_a_legacy_url(self) -> None:
        settings = Settings(  # type: ignore[call-arg]
            SECRET_KEY="test-secret-key-at-least-32-bytes-long",
            REFRESH_TOKEN_SECRET_KEY="test-refresh-token-secret-key-at-least-32-bytes-long",
            ADMIN_PASSWORD="test-admin-password",
            DATABASE_URL="postgres://user:pw@host:5432/db",
        )
        assert settings.DATABASE_URL == "postgresql://user:pw@host:5432/db"


class TestMakeAsyncUrl:
    def test_legacy_postgres_url_becomes_an_async_driver_url(self) -> None:
        assert (
            make_async_url("postgres://user:pw@host:5432/db")
            == "postgresql+psycopg://user:pw@host:5432/db"
        )

    def test_postgresql_url_becomes_an_async_driver_url(self) -> None:
        assert (
            make_async_url("postgresql://user:pw@host:5432/db")
            == "postgresql+psycopg://user:pw@host:5432/db"
        )

    def test_sqlite_url_becomes_an_async_driver_url(self) -> None:
        assert make_async_url("sqlite:///./app.db") == "sqlite+aiosqlite:///./app.db"

    @pytest.mark.parametrize(
        "url",
        [
            "postgres://user:pw@host:5432/db",
            "postgresql://user:pw@host:5432/db",
            "sqlite:///./app.db",
        ],
    )
    def test_result_resolves_to_a_real_dialect(self, url: str) -> None:
        """The production failure was NoSuchModuleError raised from dialect lookup."""
        make_url(make_async_url(url)).get_dialect()
