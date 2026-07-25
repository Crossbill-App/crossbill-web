"""Tests for how the user-registration toggle is read from the environment."""

import pytest

from src.config import Settings

_REQUIRED_ENV = {
    "SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
    "REFRESH_TOKEN_SECRET_KEY": "test-refresh-token-secret-key-at-least-32-bytes",
    "ADMIN_PASSWORD": "test-admin-password",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for name in ("ALLOW_USER_REGISTRATIONS", "ALLOW_USER_REGISTRATION"):
        monkeypatch.delenv(name, raising=False)
    for key, value in {**_REQUIRED_ENV, **env}.items():
        monkeypatch.setenv(key, value)
    # _env_file="" so the repo's own .env cannot leak into the assertions.
    return Settings(_env_file="")  # pyright: ignore[reportCallIssue]


def test_registration_is_closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _settings(monkeypatch).ALLOW_USER_REGISTRATIONS is False


def test_plural_spelling_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, ALLOW_USER_REGISTRATIONS="true")

    assert settings.ALLOW_USER_REGISTRATIONS is True


def test_singular_spelling_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """.env.example documented ALLOW_USER_REGISTRATION for a while."""
    settings = _settings(monkeypatch, ALLOW_USER_REGISTRATION="true")

    assert settings.ALLOW_USER_REGISTRATIONS is True


def test_singular_spelling_can_close_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, ALLOW_USER_REGISTRATION="false")

    assert settings.ALLOW_USER_REGISTRATIONS is False
