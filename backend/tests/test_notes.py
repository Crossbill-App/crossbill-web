"""Tests for notes API endpoints."""

from datetime import UTC, datetime

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models


class TestCreateNote:
    """Test suite for POST /notes endpoint."""

    async def test_create_note_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_chapter: models.Chapter,
        test_user: models.User,
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={
                "title": "Raskolnikov",
                "body": "Main character",
                "kind": "character",
                "book_id": test_book.id,
                "chapter_ids": [test_chapter.id],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        note = data["note"]
        assert note["title"] == "Raskolnikov"
        assert note["kind"] == "character"
        assert note["book_ids"] == [test_book.id]
        assert note["chapter_ids"] == [test_chapter.id]
        assert note["user_id"] == test_user.id
        result = await db_session.execute(select(models.Note).filter_by(id=note["id"]))
        assert result.scalar_one_or_none() is not None

    async def test_create_note_minimal(self, client: AsyncClient, test_book: models.Book) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={"title": "Stoicism", "book_id": test_book.id},
        )
        assert response.status_code == status.HTTP_201_CREATED
        note = response.json()["note"]
        assert note["body"] == ""
        assert note["kind"] is None
        assert note["chapter_ids"] == []

    async def test_create_note_book_not_found(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/notes", json={"title": "Orphan", "book_id": 99999})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_note_empty_title(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.post("/api/v1/notes", json={"title": "", "book_id": test_book.id})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_note_whitespace_title(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/notes", json={"title": "   ", "book_id": test_book.id}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_note_invalid_kind(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={"title": "X", "book_id": test_book.id, "kind": "villain"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_create_note_chapter_not_found(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={"title": "X", "book_id": test_book.id, "chapter_ids": [99999]},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_note_chapter_from_other_book_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_user: models.User,
    ) -> None:
        other_book = models.Book(user_id=test_user.id, title="Other book")
        db_session.add(other_book)
        await db_session.commit()
        await db_session.refresh(other_book)
        other_chapter = models.Chapter(book_id=other_book.id, name="Other chapter")
        db_session.add(other_chapter)
        await db_session.commit()
        await db_session.refresh(other_chapter)

        response = await client.post(
            "/api/v1/notes",
            json={"title": "X", "book_id": test_book.id, "chapter_ids": [other_chapter.id]},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_note_highlight_link_success(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_highlight: models.Highlight,
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={
                "title": "X",
                "book_id": test_book.id,
                "highlight_ids": [test_highlight.id],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        note = response.json()["note"]
        assert note["highlight_ids"] == [test_highlight.id]

    async def test_create_note_highlight_not_found(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={"title": "X", "book_id": test_book.id, "highlight_ids": [99999]},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_note_tag_link_success(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_tag: models.Tag,
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={
                "title": "X",
                "book_id": test_book.id,
                "tag_ids": [test_tag.id],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        note = response.json()["note"]
        assert note["tag_ids"] == [test_tag.id]

    async def test_create_note_tag_not_found(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.post(
            "/api/v1/notes",
            json={"title": "X", "book_id": test_book.id, "tag_ids": [99999]},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_tag_is_idempotent_for_existing_name(
        self, client: AsyncClient, test_tag: models.Tag
    ) -> None:
        # The note editor resolves a typed tag name by POSTing to /tag. A tag
        # may already exist for the book without any highlight association (so
        # it is hidden from the dropdown); re-creating it must return the
        # existing tag rather than a 409 conflict.
        response = await client.post(
            f"/api/v1/books/{test_tag.book_id}/tag",
            json={"name": test_tag.name},
        )
        assert response.status_code in (200, 201), response.text
        assert response.json()["id"] == test_tag.id


class TestGetNote:
    """Test suite for GET /notes/{note_id} endpoint."""

    async def test_get_note_with_links(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_chapter: models.Chapter,
    ) -> None:
        create = await client.post(
            "/api/v1/notes",
            json={
                "title": "Raskolnikov",
                "book_id": test_book.id,
                "chapter_ids": [test_chapter.id],
            },
        )
        note_id = create.json()["note"]["id"]

        response = await client.get(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Raskolnikov"
        assert data["chapters"] == [{"id": test_chapter.id, "name": test_chapter.name}]
        assert data["highlights"] == []
        assert data["tags"] == []
        assert data["flashcards"] == []

    async def test_get_note_includes_flashcards(
        self,
        client: AsyncClient,
        test_book: models.Book,
    ) -> None:
        create = await client.post(
            "/api/v1/notes",
            json={"title": "Raskolnikov", "book_id": test_book.id},
        )
        note_id = create.json()["note"]["id"]

        flashcard_response = await client.post(
            f"/api/v1/notes/{note_id}/flashcards",
            json={"question": "Who is Raskolnikov?", "answer": "The protagonist"},
        )
        assert flashcard_response.status_code == status.HTTP_201_CREATED
        flashcard_id = flashcard_response.json()["flashcard"]["id"]

        response = await client.get(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        flashcards = response.json()["flashcards"]
        assert len(flashcards) == 1
        assert flashcards[0]["id"] == flashcard_id
        assert flashcards[0]["question"] == "Who is Raskolnikov?"
        assert flashcards[0]["note_id"] == note_id
        assert flashcards[0]["book_id"] == test_book.id

    async def test_get_note_not_found(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/notes/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_note_populates_highlight_and_tag_summaries(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_highlight: models.Highlight,
        test_tag: models.Tag,
    ) -> None:
        create = await client.post(
            "/api/v1/notes",
            json={
                "title": "Raskolnikov",
                "book_id": test_book.id,
                "highlight_ids": [test_highlight.id],
                "tag_ids": [test_tag.id],
            },
        )
        note_id = create.json()["note"]["id"]

        response = await client.get(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["highlights"] == [{"id": test_highlight.id, "text": test_highlight.text}]
        assert data["tags"] == [{"id": test_tag.id, "name": test_tag.name}]

    async def test_get_note_cross_user_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        result = await db_session.execute(select(models.User).filter_by(id=2))
        other_user = result.scalar_one_or_none()
        if other_user is None:
            other_user = models.User(id=2, email="other@test.com")
            db_session.add(other_user)
            await db_session.commit()

        other_note = models.Note(user_id=other_user.id, title="Not yours", body="")
        db_session.add(other_note)
        await db_session.commit()
        await db_session.refresh(other_note)

        response = await client.get(f"/api/v1/notes/{other_note.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_note_excludes_soft_deleted_highlight(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_highlight: models.Highlight,
    ) -> None:
        create = await client.post(
            "/api/v1/notes",
            json={
                "title": "X",
                "book_id": test_book.id,
                "highlight_ids": [test_highlight.id],
            },
        )
        note_id = create.json()["note"]["id"]

        test_highlight.deleted_at = datetime.now(UTC)
        db_session.add(test_highlight)
        await db_session.commit()

        response = await client.get(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["highlights"] == []


class TestGetNotesForBook:
    """Test suite for GET /books/{book_id}/notes endpoint."""

    @pytest.fixture
    async def two_notes(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_chapter: models.Chapter,
    ) -> tuple[int, int]:
        """Create a character note (linked to chapter) and a concept note."""
        first = await client.post(
            "/api/v1/notes",
            json={
                "title": "Raskolnikov",
                "kind": "character",
                "book_id": test_book.id,
                "chapter_ids": [test_chapter.id],
            },
        )
        second = await client.post(
            "/api/v1/notes",
            json={"title": "Nihilism", "kind": "concept", "book_id": test_book.id},
        )
        return first.json()["note"]["id"], second.json()["note"]["id"]

    async def test_list_notes(
        self, client: AsyncClient, test_book: models.Book, two_notes: tuple[int, int]
    ) -> None:
        response = await client.get(f"/api/v1/books/{test_book.id}/notes")
        assert response.status_code == status.HTTP_200_OK
        notes = response.json()["items"]
        assert len(notes) == 2

    async def test_list_includes_tag_not_attached_to_any_highlight(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        # A tag linked to a note but NOT to any highlight must still appear in
        # the note's tag summary in the list response.
        tag_resp = await client.post(
            f"/api/v1/books/{test_book.id}/tag",
            json={"name": "note-only"},
        )
        assert tag_resp.status_code in (200, 201), tag_resp.text
        tag_id = tag_resp.json()["id"]

        await client.post(
            "/api/v1/notes",
            json={
                "title": "Concept",
                "book_id": test_book.id,
                "tag_ids": [tag_id],
            },
        )

        response = await client.get(f"/api/v1/books/{test_book.id}/notes")
        note = next(n for n in response.json()["items"] if n["title"] == "Concept")
        assert note["tag_ids"] == [tag_id]
        assert [t["id"] for t in note["tags"]] == [tag_id]

    async def test_list_notes_includes_link_summaries(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_chapter: models.Chapter,
        two_notes: tuple[int, int],
    ) -> None:
        response = await client.get(f"/api/v1/books/{test_book.id}/notes")
        notes = response.json()["items"]
        raskolnikov = next(n for n in notes if n["title"] == "Raskolnikov")
        assert raskolnikov["chapters"] == [{"id": test_chapter.id, "name": test_chapter.name}]

    async def test_list_notes_includes_flashcards(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        # The frontend seeds the note-detail cache from a list row, so a list
        # row must carry everything the detail carries.
        create = await client.post(
            "/api/v1/notes", json={"title": "Raskolnikov", "book_id": test_book.id}
        )
        note_id = create.json()["note"]["id"]
        await client.post(
            f"/api/v1/notes/{note_id}/flashcards",
            json={"question": "Who is Raskolnikov?", "answer": "The protagonist"},
        )

        response = await client.get(f"/api/v1/books/{test_book.id}/notes")
        (note,) = response.json()["items"]
        assert [f["question"] for f in note["flashcards"]] == ["Who is Raskolnikov?"]

    async def test_list_excludes_soft_deleted_highlight(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
        test_highlight: models.Highlight,
    ) -> None:
        # The mirror of test_get_note_excludes_soft_deleted_highlight: the list
        # view must hide a deleted highlight exactly as the detail view does.
        await client.post(
            "/api/v1/notes",
            json={
                "title": "X",
                "book_id": test_book.id,
                "highlight_ids": [test_highlight.id],
            },
        )

        test_highlight.deleted_at = datetime.now(UTC)
        db_session.add(test_highlight)
        await db_session.commit()

        response = await client.get(f"/api/v1/books/{test_book.id}/notes")
        assert response.status_code == status.HTTP_200_OK
        note = next(n for n in response.json()["items"] if n["title"] == "X")
        assert note["highlights"] == []

    async def test_list_notes_filter_by_kind(
        self, client: AsyncClient, test_book: models.Book, two_notes: tuple[int, int]
    ) -> None:
        response = await client.get(f"/api/v1/books/{test_book.id}/notes?kind=character")
        notes = response.json()["items"]
        assert len(notes) == 1
        assert notes[0]["title"] == "Raskolnikov"

    async def test_list_notes_filter_by_gist_kind(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_chapter: models.Chapter,
    ) -> None:
        await client.post(
            "/api/v1/notes",
            json={
                "title": test_chapter.name,
                "body": "This chapter is about the crime.",
                "kind": "gist",
                "book_id": test_book.id,
                "chapter_ids": [test_chapter.id],
            },
        )

        gist_resp = await client.get(f"/api/v1/books/{test_book.id}/notes?kind=gist")
        gists = gist_resp.json()["items"]
        assert len(gists) == 1
        assert gists[0]["kind"] == "gist"
        assert gists[0]["chapter_ids"] == [test_chapter.id]

        concept_resp = await client.get(f"/api/v1/books/{test_book.id}/notes?kind=concept")
        assert concept_resp.json()["items"] == []

    async def test_list_notes_filter_by_chapter(
        self,
        client: AsyncClient,
        test_book: models.Book,
        test_chapter: models.Chapter,
        two_notes: tuple[int, int],
    ) -> None:
        response = await client.get(
            f"/api/v1/books/{test_book.id}/notes?chapter_id={test_chapter.id}"
        )
        notes = response.json()["items"]
        assert len(notes) == 1
        assert notes[0]["title"] == "Raskolnikov"

    async def test_list_notes_empty(self, client: AsyncClient, test_book: models.Book) -> None:
        response = await client.get(f"/api/v1/books/{test_book.id}/notes")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_notes_book_not_found(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/books/99999/notes")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateNote:
    """Test suite for PUT /notes/{note_id} endpoint."""

    @pytest.fixture
    async def note_id(
        self, client: AsyncClient, test_book: models.Book, test_chapter: models.Chapter
    ) -> int:
        response = await client.post(
            "/api/v1/notes",
            json={
                "title": "Raskolnikov",
                "kind": "character",
                "book_id": test_book.id,
                "chapter_ids": [test_chapter.id],
            },
        )
        return response.json()["note"]["id"]

    async def test_update_note_links_freshly_created_tag(
        self,
        client: AsyncClient,
        note_id: int,
        test_book: models.Book,
    ) -> None:
        # Simulate the note editor: create a brand-new highlight tag, then
        # PUT the note referencing that tag's id.
        tag_resp = await client.post(
            f"/api/v1/books/{test_book.id}/tag",
            json={"name": "freshly-created"},
        )
        assert tag_resp.status_code in (200, 201), tag_resp.text
        tag_id = tag_resp.json()["id"]

        put_resp = await client.put(
            f"/api/v1/notes/{note_id}",
            json={
                "title": "Raskolnikov",
                "body": "",
                "kind": "character",
                "chapter_ids": [],
                "highlight_ids": [],
                "tag_ids": [tag_id],
            },
        )
        assert put_resp.status_code == status.HTTP_200_OK, put_resp.text
        assert put_resp.json()["note"]["tag_ids"] == [tag_id]

        get_resp = await client.get(f"/api/v1/notes/{note_id}")
        assert get_resp.json()["tag_ids"] == [tag_id]
        assert [t["id"] for t in get_resp.json()["tags"]] == [tag_id]

    async def test_update_note_fields_and_links(
        self,
        client: AsyncClient,
        note_id: int,
        test_highlight: models.Highlight,
    ) -> None:
        response = await client.put(
            f"/api/v1/notes/{note_id}",
            json={
                "title": "Rodion Raskolnikov",
                "body": "Updated body",
                "kind": "character",
                "chapter_ids": [],
                "highlight_ids": [test_highlight.id],
                "tag_ids": [],
            },
        )
        assert response.status_code == status.HTTP_200_OK
        note = response.json()["note"]
        assert note["title"] == "Rodion Raskolnikov"
        assert note["body"] == "Updated body"
        assert note["chapter_ids"] == []
        assert note["highlight_ids"] == [test_highlight.id]

    async def test_update_note_not_found(self, client: AsyncClient) -> None:
        response = await client.put(
            "/api/v1/notes/99999",
            json={"title": "X", "body": "", "kind": None},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_note_invalid_chapter(self, client: AsyncClient, note_id: int) -> None:
        response = await client.put(
            f"/api/v1/notes/{note_id}",
            json={"title": "X", "body": "", "kind": None, "chapter_ids": [99999]},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_note_whitespace_title(self, client: AsyncClient, note_id: int) -> None:
        response = await client.put(
            f"/api/v1/notes/{note_id}",
            json={"title": "   ", "body": "", "kind": None},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestDeleteNote:
    """Test suite for DELETE /notes/{note_id} endpoint."""

    async def test_delete_note(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
    ) -> None:
        create = await client.post(
            "/api/v1/notes", json={"title": "Doomed", "book_id": test_book.id}
        )
        note_id = create.json()["note"]["id"]

        response = await client.delete(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        result = await db_session.execute(select(models.Note).filter_by(id=note_id))
        assert result.scalar_one_or_none() is None

    async def test_delete_note_not_found(self, client: AsyncClient) -> None:
        response = await client.delete("/api/v1/notes/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_note_deleted_when_book_deleted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: models.Book,
    ) -> None:
        create = await client.post(
            "/api/v1/notes", json={"title": "Cascade", "book_id": test_book.id}
        )
        note_id = create.json()["note"]["id"]

        response = await client.delete(f"/api/v1/books/{test_book.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # The note_books link row is gone; the note itself remains (user-scoped)
        # but is no longer reachable via any book listing.
        result = await db_session.execute(select(models.note_books).filter_by(note_id=note_id))
        assert result.first() is None
