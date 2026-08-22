"""The client-version gate over the endpoints only the KOReader plugin calls.

Driven through the endpoints because the gate is a property of the surface, not
of a function: which routes carry it is half of what can go wrong.
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.infrastructure.common.client_version import (
    CLIENT_VERSION_HEADER,
    CLIENT_VERSION_REQUIREMENTS,
    KOREADER_PLUGIN,
    UPGRADE_REQUIRED_CODE,
    format_version,
)
from src.infrastructure.identity.services.password_service import hash_password
from src.main import app
from src.models import User
from tests.conftest import create_test_book

REQUIREMENT = CLIENT_VERSION_REQUIREMENTS[KOREADER_PLUGIN]
MIN_VERSION = format_version(REQUIREMENT.min_version)

CLIENT_BOOK_ID = "gated-book"

HIGHLIGHT_UPLOAD = {
    "client_book_id": CLIENT_BOOK_ID,
    "highlights": [
        {
            "text": "A sentence worth keeping",
            "datetime": "2026-01-15 14:30:22",
        }
    ],
}

SESSION_UPLOAD = {
    "client_book_id": CLIENT_BOOK_ID,
    "sessions": [
        {
            "start_time": "2026-01-15T10:00:00Z",
            "end_time": "2026-01-15T11:00:00Z",
            "device_id": "kobo-1",
        }
    ],
}


def expected_detail(received_version: str | None) -> dict[str, Any]:
    return {
        "code": UPGRADE_REQUIRED_CODE,
        "client": KOREADER_PLUGIN,
        "min_supported_version": MIN_VERSION,
        "received_version": received_version,
        "update_url": REQUIREMENT.update_url,
    }


@pytest.fixture
async def gated_book(db_session: AsyncSession) -> models.Book:
    """A book the plugin would address by its client_book_id."""
    return await create_test_book(
        db_session=db_session,
        user_id=1,
        title="Gated Book",
        client_book_id=CLIENT_BOOK_ID,
    )


@pytest.fixture
async def headerless_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """A client sending no X-Crossbill-Client header, as old plugins do.

    Built on top of ``client`` so the app-wide overrides that fixture installs
    (database session, current user, file repository, job queue) are in place;
    only the default header the shared client carries is dropped.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare_client:
        yield bare_client


async def test_ereader_route_rejects_a_client_that_names_none(
    headerless_client: AsyncClient, gated_book: models.Book
) -> None:
    response = await headerless_client.get(f"/api/v1/ereader/books/{CLIENT_BOOK_ID}")

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=None)


async def test_highlight_upload_rejects_a_client_that_names_none(
    headerless_client: AsyncClient, db_session: AsyncSession, gated_book: models.Book
) -> None:
    response = await headerless_client.post("/api/v1/highlights/upload", json=HIGHLIGHT_UPLOAD)

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=None)

    stored = await db_session.execute(select(models.Highlight))
    assert stored.scalars().all() == []


async def test_reading_session_upload_rejects_a_client_that_names_none(
    headerless_client: AsyncClient, db_session: AsyncSession, gated_book: models.Book
) -> None:
    response = await headerless_client.post("/api/v1/reading_sessions/upload", json=SESSION_UPLOAD)

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=None)

    stored = await db_session.execute(select(models.ReadingSession))
    assert stored.scalars().all() == []


@pytest.mark.parametrize(
    "version",
    [
        "0.12.0",
        # Below the minimum on the numbers and above it as a string: the one
        # case that tells a version comparison from a lexicographic one.
        "0.9.0",
    ],
)
async def test_version_below_the_minimum_is_rejected(
    headerless_client: AsyncClient, gated_book: models.Book, version: str
) -> None:
    response = await headerless_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_VERSION_HEADER: f"{KOREADER_PLUGIN}/{version}"},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=version)


@pytest.mark.parametrize(
    "version",
    [
        "banana",
        "v0.13.0",
        # Two parts only. A lenient parse would read this as newer than the
        # minimum and let it through.
        "1.2",
        "0.13.0-beta.1",
        "",
    ],
)
async def test_version_we_cannot_read_is_rejected(
    headerless_client: AsyncClient, gated_book: models.Book, version: str
) -> None:
    """Fail closed: an unreadable version is not evidence of a new enough client."""
    response = await headerless_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_VERSION_HEADER: f"{KOREADER_PLUGIN}/{version}"},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=None)


async def test_an_oversized_version_number_is_rejected_not_crashed(
    headerless_client: AsyncClient, gated_book: models.Book
) -> None:
    """``int()`` refuses more than 4300 digits, and this route runs before auth.

    An unbounded pattern would hand the segment to ``int``, which raises, and
    any stranger could turn a header into a 500 without logging in.
    """
    response = await headerless_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_VERSION_HEADER: f"{KOREADER_PLUGIN}/1.1.{'9' * 5000}"},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=None)


@pytest.mark.parametrize("header_value", ["", "   "])
async def test_a_header_that_names_no_client_is_rejected(
    headerless_client: AsyncClient, gated_book: models.Book, header_value: str
) -> None:
    """An empty value names no client, so it cannot pass as an unknown one."""
    response = await headerless_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_VERSION_HEADER: header_value},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json()["detail"] == expected_detail(received_version=None)


@pytest.mark.parametrize(
    "version",
    [
        MIN_VERSION,
        format_version((REQUIREMENT.min_version[0], REQUIREMENT.min_version[1], 99)),
        format_version((REQUIREMENT.min_version[0] + 1, 0, 0)),
    ],
)
async def test_version_at_or_above_the_minimum_is_served(
    headerless_client: AsyncClient, gated_book: models.Book, version: str
) -> None:
    response = await headerless_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_VERSION_HEADER: f"{KOREADER_PLUGIN}/{version}"},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["bookname"] == "Gated Book"


async def test_client_we_have_no_requirement_for_is_served(
    headerless_client: AsyncClient, gated_book: models.Book
) -> None:
    """The gate polices our own clients' versions, not who may call the API."""
    response = await headerless_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_VERSION_HEADER: "someones-script/0.0.1"},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["bookname"] == "Gated Book"


async def test_ungated_endpoint_serves_a_client_that_names_none(
    headerless_client: AsyncClient, gated_book: models.Book
) -> None:
    """The web app sends no such header and must keep working."""
    response = await headerless_client.get("/api/v1/books/")

    assert response.status_code == status.HTTP_200_OK, response.text
    assert [book["title"] for book in response.json()["items"]] == ["Gated Book"]


async def test_login_serves_a_client_that_names_none(
    headerless_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    """A plugin too old to be served still has to be able to authenticate."""
    password = "correct-horse-battery-staple"
    test_user.hashed_password = await hash_password(password)
    await db_session.commit()

    response = await headerless_client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": password},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["access_token"]
