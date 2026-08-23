"""Public app settings endpoint: feature flags plus the running release version."""

import tomllib

from httpx import AsyncClient

from src.config import BACKEND_ROOT


def _manifest_version() -> str:
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


async def test_settings_reports_the_version_from_the_manifest(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == _manifest_version()
    assert body["version"] != "unknown"
    assert "feature_flags" in body
