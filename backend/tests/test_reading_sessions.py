"""Tests for reading sessions API endpoints."""

import uuid
from datetime import UTC, datetime
from typing import NamedTuple

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from tests.conftest import create_test_book

# Default user ID used by services (matches conftest default user)
DEFAULT_USER_ID = 1


# --- NamedTuples for composite fixtures ---


class BookWithSessions(NamedTuple):
    book: models.Book
    sessions: list[models.ReadingSession]


# --- Fixtures for common test data ---


@pytest.fixture
async def test_book(db_session: AsyncSession) -> models.Book:
    """Create a test book with default values."""
    return await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Test Book",
        author="Test Author",
        client_book_id="test-client-book-id",
    )


@pytest.fixture
async def test_reading_session(
    db_session: AsyncSession, test_book: models.Book
) -> models.ReadingSession:
    """Create a test reading session for the test book."""
    return await create_reading_session(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
        device_id="test-device-1",
        start_xpoint="/body/div[1]/p[1]",
        end_xpoint="/body/div[1]/p[50]",
    )


@pytest.fixture
async def book_with_sessions(db_session: AsyncSession, test_book: models.Book) -> BookWithSessions:
    """Create a test book with multiple reading sessions."""
    session1 = await create_reading_session(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
        device_id="device-1",
        start_page=10,
        end_page=15,
    )
    session2 = await create_reading_session(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        start_time=datetime(2024, 1, 16, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2024, 1, 16, 11, 0, 0, tzinfo=UTC),
        device_id="device-1",
        start_page=16,
        end_page=25,
    )
    return BookWithSessions(book=test_book, sessions=[session1, session2])


async def create_reading_session(
    db_session: AsyncSession,
    book: models.Book,
    user_id: int,
    start_time: datetime,
    end_time: datetime,
    device_id: str | None = None,
    start_xpoint: str | None = None,
    end_xpoint: str | None = None,
    start_page: int | None = None,
    end_page: int | None = None,
) -> models.ReadingSession:
    """Helper function to create a reading session."""
    session = models.ReadingSession(
        user_id=user_id,
        book_id=book.id,
        start_time=start_time,
        end_time=end_time,
        start_xpoint=start_xpoint,
        end_xpoint=end_xpoint,
        start_page=start_page,
        end_page=end_page,
        device_id=device_id,
        content_hash=str(uuid.uuid4()),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


class TestUploadReadingSessions:
    """Test suite for POST /reading_sessions/upload endpoint."""

    async def test_upload_single_session_success(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test successful upload of a single reading session."""
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "start_xpoint": "/body/div[1]/p[1]",
                        "end_xpoint": "/body/div[1]/p[50]",
                        "device_id": "kindle-123",
                    }
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["created_count"] == 1
        assert data["skipped_duplicate_count"] == 0

        # Verify session was created in database with correct values
        result = await db_session.execute(select(models.ReadingSession))
        session = result.scalar_one_or_none()
        assert session is not None
        assert session.book_id == test_book.id
        assert session.device_id == "kindle-123"
        # Compare with timezone-aware datetimes (use replace to normalize for SQLite)
        assert session.start_time.replace(tzinfo=UTC) == datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert session.end_time.replace(tzinfo=UTC) == datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
        assert session.start_xpoint == "/body/DocFragment[1]/body/div[1]/p[1]"
        assert session.end_xpoint == "/body/DocFragment[1]/body/div[1]/p[50]"

    async def test_upload_bulk_sessions_success(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test successful bulk upload of multiple sessions for a single book."""
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "device_id": "device-1",
                        "start_page": 10,
                        "end_page": 15,
                    },
                    {
                        "start_time": "2024-01-16T10:00:00Z",
                        "end_time": "2024-01-16T11:00:00Z",
                        "device_id": "device-1",
                        "start_page": 16,
                        "end_page": 20,
                    },
                    {
                        "start_time": "2024-01-17T10:00:00Z",
                        "end_time": "2024-01-17T11:00:00Z",
                        "device_id": "device-1",
                        "start_page": 21,
                        "end_page": 25,
                    },
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["created_count"] == 3

        # Verify all sessions were created for the same book
        result = await db_session.execute(
            select(models.ReadingSession).filter_by(book_id=test_book.id)
        )
        sessions = result.scalars().all()
        assert len(sessions) == 3

        # Verify session details
        assert sessions[0].device_id == "device-1"
        assert sessions[0].start_page == 10
        assert sessions[2].end_page == 25

    async def test_upload_duplicate_sessions_skipped(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test that duplicate sessions are skipped and reported in count."""
        session_data = {
            "client_book_id": "test-client-book-id",
            "sessions": [
                {
                    "start_time": "2024-01-15T10:00:00Z",
                    "end_time": "2024-01-15T11:00:00Z",
                    "device_id": "kindle-123",
                    "start_page": 10,
                    "end_page": 15,
                }
            ],
        }

        # First upload
        response1 = await client.post("/api/v1/reading_sessions/upload", json=session_data)
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["created_count"] == 1
        assert data1["skipped_duplicate_count"] == 0

        # Second upload (duplicate)
        response2 = await client.post("/api/v1/reading_sessions/upload", json=session_data)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["created_count"] == 0
        assert data2["skipped_duplicate_count"] == 1

        # Verify only one session exists
        result = await db_session.execute(select(models.ReadingSession))
        sessions = result.scalars().all()
        assert len(sessions) == 1

    async def test_upload_same_time_different_device_allowed(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test that same start time from different devices is allowed."""
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "device_id": "device-1",
                        "start_page": 10,
                        "end_page": 15,
                    },
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "device_id": "device-2",
                        "start_page": 10,
                        "end_page": 15,
                    },
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify both sessions were created with different device IDs
        result = await db_session.execute(select(models.ReadingSession))
        sessions = result.scalars().all()
        assert len(sessions) == 2
        device_ids = {s.device_id for s in sessions}
        assert device_ids == {"device-1", "device-2"}

    async def test_upload_session_with_page_positions(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test uploading a session with page positions."""
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "start_page": 10,
                        "end_page": 25,
                    }
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify session was created with correct page positions
        result = await db_session.execute(select(models.ReadingSession))
        session = result.scalar_one_or_none()
        assert session is not None
        assert session.book_id == test_book.id
        assert session.start_page == 10
        assert session.end_page == 25
        assert session.start_xpoint is None
        assert session.end_xpoint is None

    async def test_filter_sessions_with_same_pages_for_start_and_end(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "start_page": 10,
                        "end_page": 10,
                    }
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify session was created with correct page positions
        result = await db_session.execute(select(models.ReadingSession))
        session = result.scalar_one_or_none()
        assert session is None

    async def test_filter_sessions_with_same_xpoints_for_start_and_end(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "start_xpoint": "/body/div[1]/p[1]",
                        "end_xpoint": "/body/div[1]/p[1]",
                    }
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify session was created with correct page positions
        result = await db_session.execute(select(models.ReadingSession))
        session = result.scalar_one_or_none()
        assert session is None

    async def test_not_filter_sessions_with_same_pages_for_start_and_end_but_different_points(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={
                "client_book_id": "test-client-book-id",
                "sessions": [
                    {
                        "start_time": "2024-01-15T10:00:00Z",
                        "end_time": "2024-01-15T11:00:00Z",
                        "start_xpoint": "/body/div[1]/p[1]",
                        "end_xpoint": "/body/div[5]/p[1]",
                        "start_page": 10,
                        "end_page": 10,
                    }
                ],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify session was created with correct page positions
        result = await db_session.execute(select(models.ReadingSession))
        session = result.scalar_one_or_none()
        assert session is not None

    @pytest.mark.parametrize(
        "sessions",
        [
            # Missing required start_time
            [{"end_time": "2024-01-15T11:00:00Z", "start_page": 10, "end_page": 25}],
            # Missing both position types
            [{"start_time": "2024-01-15T10:00:00Z", "end_time": "2024-01-15T11:00:00Z"}],
            # Invalid datetime format
            [
                {
                    "start_time": "invalid-date",
                    "end_time": "2024-01-15T11:00:00Z",
                    "start_page": 10,
                    "end_page": 25,
                }
            ],
            # Mix of valid and invalid sessions (all-or-nothing)
            [
                {
                    "start_time": "2024-01-15T10:00:00Z",
                    "end_time": "2024-01-15T11:00:00Z",
                    "start_page": 10,
                    "end_page": 25,
                },
                {"start_time": "2024-01-16T10:00:00Z", "end_time": "2024-01-16T11:00:00Z"},
            ],
        ],
        ids=[
            "missing_required_field",
            "missing_positions",
            "invalid_datetime",
            "mixed_valid_invalid",
        ],
    )
    async def test_upload_invalid_sessions_returns_422(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        sessions: list[dict[str, object]],
    ) -> None:
        """Test that invalid session payloads return 422 and nothing is saved."""
        response = await client.post(
            "/api/v1/reading_sessions/upload",
            json={"client_book_id": "test-client-book-id", "sessions": sessions},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Verify nothing was saved to database
        result = await db_session.execute(select(models.ReadingSession))
        sessions_in_db = result.scalars().all()
        assert len(sessions_in_db) == 0


class TestGetBookReadingSessions:
    """Test suite for GET /books/:id/reading_sessions endpoint."""

    async def test_get_sessions_success(
        self, client: AsyncClient, book_with_sessions: BookWithSessions
    ) -> None:
        """Test successful retrieval of reading sessions for a book."""
        book, sessions = book_with_sessions

        response = await client.get(f"/api/v1/books/{book.id}/reading_sessions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["total"] == 2

        # Verify session data matches database records
        returned_ids = {s["id"] for s in data["items"]}
        expected_ids = {s.id for s in sessions}
        assert returned_ids == expected_ids

    async def test_get_sessions_ordered_by_start_time_desc(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test that sessions are ordered by start_time descending (newest first)."""
        older_session = await create_reading_session(
            db_session=db_session,
            book=test_book,
            user_id=DEFAULT_USER_ID,
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
            device_id="device-older",
            start_page=10,
            end_page=15,
        )
        newer_session = await create_reading_session(
            db_session=db_session,
            book=test_book,
            user_id=DEFAULT_USER_ID,
            start_time=datetime(2024, 1, 17, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 17, 11, 0, 0, tzinfo=UTC),
            device_id="device-newer",
            start_page=16,
            end_page=25,
        )

        response = await client.get(f"/api/v1/books/{test_book.id}/reading_sessions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        sessions = data["items"]

        # Newer session should come first
        assert sessions[0]["id"] == newer_session.id
        assert sessions[0]["device_id"] == "device-newer"
        assert sessions[1]["id"] == older_session.id
        assert sessions[1]["device_id"] == "device-older"

    async def test_get_sessions_empty(self, client: AsyncClient, test_book: models.Book) -> None:
        """Test getting sessions when book has none."""
        response = await client.get(f"/api/v1/books/{test_book.id}/reading_sessions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_sessions_book_not_found(self, client: AsyncClient) -> None:
        """Test getting sessions for non-existent book."""
        response = await client.get("/api/v1/books/99999/reading_sessions")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_sessions_pagination(
        self, client: AsyncClient, db_session: AsyncSession, test_book: models.Book
    ) -> None:
        """Test pagination of reading sessions."""
        for i in range(5):
            await create_reading_session(
                db_session=db_session,
                book=test_book,
                user_id=DEFAULT_USER_ID,
                start_time=datetime(2024, 1, 15 + i, 10, 0, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 15 + i, 11, 0, 0, tzinfo=UTC),
                device_id=f"device-{i}",
                start_page=10,
                end_page=15,
            )

        # Get first 2
        response = await client.get(
            f"/api/v1/books/{test_book.id}/reading_sessions?limit=2&offset=0"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

        # Get next 2
        response = await client.get(
            f"/api/v1/books/{test_book.id}/reading_sessions?limit=2&offset=2"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) == 2


class TestReadingSessionCascadeDelete:
    """Test suite for cascade deletion of reading sessions."""

    async def test_sessions_deleted_when_book_deleted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_reading_session: models.ReadingSession,
    ) -> None:
        """Test that reading sessions are deleted when book is deleted."""
        session_id = test_reading_session.id

        response = await client.delete(f"/api/v1/books/{test_book.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify session was cascade deleted
        result = await db_session.execute(select(models.ReadingSession).filter_by(id=session_id))
        deleted_session = result.scalar_one_or_none()
        assert deleted_session is None
