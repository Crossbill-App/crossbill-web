"""The client-version gate over the endpoints only the KOReader plugin calls.

Driven through the endpoints because the gate is a property of the surface, not
of a function: which routes carry it is half of what can go wrong.

Every value of the contract -- the header name, the minimum version, the code
and the update URL -- is written out as a literal here rather than read from
``client_version``. Deriving them from the module under test would mean a wrong
minimum still matched itself and the whole file stayed green; a plugin in the
wild reads these strings, so a test has to say them out loud.
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.identity.services.password_service import hash_password
from src.main import app
from src.models import User
from tests.conftest import create_test_book

CLIENT_HEADER = "X-Crossbill-Client"
PLUGIN = "koreader-plugin"
MIN_VERSION = "0.13.0"
UPGRADE_REQUIRED_CODE = "client_upgrade_required"
UPDATE_URL = "https://github.com/Crossbill-App/koreader-plugin"

CLIENT_BOOK_ID = "gated-book"

# The whole plugin-only surface: the five ereader routes plus the two uploads
# that live on otherwise ungated routers. ``test_route_tree`` holds this list to
# the app's own routing table, so a new gated route that is missing here fails
# there rather than going untested.
GATED_ROUTES: list[tuple[str, str]] = [
    ("POST", "/api/v1/ereader/books"),
    ("GET", f"/api/v1/ereader/books/{CLIENT_BOOK_ID}"),
    ("POST", f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub"),
    ("GET", f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/digest"),
    ("GET", f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/highlights"),
    ("POST", "/api/v1/highlights/upload"),
    ("POST", "/api/v1/reading_sessions/upload"),
]

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


def expected_body(received_version: str | None) -> dict[str, Any]:
    """The entire 426 response body, not only its ``detail``.

    A plugin parses this whole document, so an extra top-level key -- or the
    detail arriving as a bare string -- is a contract change either way.
    """
    return {
        "detail": {
            "code": UPGRADE_REQUIRED_CODE,
            "client": PLUGIN,
            "min_supported_version": MIN_VERSION,
            "received_version": received_version,
            "update_url": UPDATE_URL,
        }
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
async def unauthenticated_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """A client with no current-user override, so authentication really runs.

    Built on ``client`` for the database and container overrides, then drops the
    one override that would hide the order the gate and the login check run in.
    """
    app.dependency_overrides.pop(get_current_user, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare_client:
        yield bare_client


@pytest.mark.parametrize(
    ("method", "path"),
    GATED_ROUTES,
    ids=[f"{method} {path}" for method, path in GATED_ROUTES],
)
async def test_every_gated_route_rejects_a_client_that_names_none(
    client: AsyncClient, gated_book: models.Book, method: str, path: str
) -> None:
    """The gate answers before the body is read, so an empty request is enough."""
    response = await client.request(method, path)

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json() == expected_body(received_version=None)


async def test_highlight_upload_writes_nothing_for_a_client_that_names_none(
    client: AsyncClient, db_session: AsyncSession, gated_book: models.Book
) -> None:
    response = await client.post("/api/v1/highlights/upload", json=HIGHLIGHT_UPLOAD)

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    stored = await db_session.execute(select(models.Highlight))
    assert stored.scalars().all() == []


async def test_reading_session_upload_writes_nothing_for_a_client_that_names_none(
    client: AsyncClient, db_session: AsyncSession, gated_book: models.Book
) -> None:
    response = await client.post("/api/v1/reading_sessions/upload", json=SESSION_UPLOAD)

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    stored = await db_session.execute(select(models.ReadingSession))
    assert stored.scalars().all() == []


async def test_an_outdated_plugin_is_turned_away_before_it_authenticates(
    unauthenticated_client: AsyncClient, gated_book: models.Book
) -> None:
    """A plugin too old to be served learns that, not that its token is missing.

    The 401 half is the control: without it this passes on a route that answers
    426 to everyone, authenticated or not.
    """
    outdated = await unauthenticated_client.get(f"/api/v1/ereader/books/{CLIENT_BOOK_ID}")

    assert outdated.status_code == status.HTTP_426_UPGRADE_REQUIRED, outdated.text
    assert outdated.json() == expected_body(received_version=None)

    current = await unauthenticated_client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: f"{PLUGIN}/{MIN_VERSION}"},
    )

    assert current.status_code == status.HTTP_401_UNAUTHORIZED, current.text


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
    client: AsyncClient, gated_book: models.Book, version: str
) -> None:
    response = await client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: f"{PLUGIN}/{version}"},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json() == expected_body(received_version=version)


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
    client: AsyncClient, gated_book: models.Book, version: str
) -> None:
    """Fail closed: an unreadable version is not evidence of a new enough client."""
    response = await client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: f"{PLUGIN}/{version}"},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json() == expected_body(received_version=None)


async def test_an_oversized_version_number_is_rejected_not_crashed(
    client: AsyncClient, gated_book: models.Book
) -> None:
    """``int()`` refuses more than 4300 digits, and this route runs before auth.

    An unbounded pattern would hand the segment to ``int``, which raises, and
    any stranger could turn a header into a 500 without logging in.
    """
    response = await client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: f"{PLUGIN}/1.1.{'9' * 5000}"},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json() == expected_body(received_version=None)


@pytest.mark.parametrize("header_value", ["", "   "])
async def test_a_header_that_names_no_client_is_rejected(
    client: AsyncClient, gated_book: models.Book, header_value: str
) -> None:
    """An empty value names no client, so it cannot pass as an unknown one."""
    response = await client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: header_value},
    )

    assert response.status_code == status.HTTP_426_UPGRADE_REQUIRED, response.text
    assert response.json() == expected_body(received_version=None)


@pytest.mark.parametrize("version", [MIN_VERSION, "0.13.99", "1.0.0"])
async def test_version_at_or_above_the_minimum_is_served(
    client: AsyncClient, gated_book: models.Book, version: str
) -> None:
    response = await client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: f"{PLUGIN}/{version}"},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["bookname"] == "Gated Book"


async def test_client_we_have_no_requirement_for_is_served(
    client: AsyncClient, gated_book: models.Book
) -> None:
    """The gate polices our own clients' versions, not who may call the API."""
    response = await client.get(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}",
        headers={CLIENT_HEADER: "someones-script/0.0.1"},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["bookname"] == "Gated Book"


async def test_ungated_endpoint_serves_a_client_that_names_none(
    client: AsyncClient, gated_book: models.Book
) -> None:
    """The web app sends no such header and must keep working."""
    response = await client.get("/api/v1/books/")

    assert response.status_code == status.HTTP_200_OK, response.text
    assert [book["title"] for book in response.json()["items"]] == ["Gated Book"]


async def test_login_serves_a_client_that_names_none(
    client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    """A plugin too old to be served still has to be able to authenticate."""
    password = "correct-horse-battery-staple"
    test_user.hashed_password = await hash_password(password)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": password},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["access_token"]
