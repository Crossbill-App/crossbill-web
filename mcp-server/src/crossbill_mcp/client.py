"""Crossbill REST API client with JWT authentication."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CrossbillClient:
    """HTTP client for the Crossbill REST API.

    Handles JWT authentication, token refresh, and API calls.
    """

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _login(self) -> None:
        """Authenticate with email/password and store tokens."""
        response = await self._client.post(
            "/api/v1/auth/login",
            data={"username": self.email, "password": self.password},
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        logger.info("Authenticated with Crossbill API")

    async def _refresh(self) -> bool:
        """Try to refresh the access token. Returns True on success."""
        if not self._refresh_token:
            return False
        try:
            response = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": self._refresh_token},
            )
            if response.status_code == 200:
                data = response.json()
                self._access_token = data["access_token"]
                self._refresh_token = data.get("refresh_token", self._refresh_token)
                logger.info("Refreshed access token")
                return True
        except httpx.HTTPError:
            pass
        return False

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an authenticated API request with automatic token management."""
        if not self._access_token:
            await self._login()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        response = await self._client.request(method, path, headers=headers, **kwargs)

        # If unauthorized, try refresh then re-login
        if response.status_code == 401:
            refreshed = await self._refresh()
            if not refreshed:
                await self._login()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            response = await self._client.request(
                method, path, headers=headers, **kwargs
            )

        response.raise_for_status()
        return response

    # --- Book endpoints ---

    async def list_books(
        self,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """List books with optional search and pagination."""
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        response = await self._request("GET", "/api/v1/books/", params=params)
        return response.json()

    async def get_book(self, book_id: int) -> dict:
        """Get detailed book information with chapters and highlights."""
        response = await self._request("GET", f"/api/v1/books/{book_id}")
        return response.json()

    async def get_recently_viewed_books(self, limit: int = 10) -> dict:
        """Get recently viewed books."""
        response = await self._request(
            "GET", "/api/v1/books/recently-viewed", params={"limit": limit}
        )
        return response.json()

    # --- Highlight endpoints ---

    async def search_highlights(self, book_id: int, search_text: str) -> dict:
        """Search highlights in a book."""
        response = await self._request(
            "GET",
            f"/api/v1/books/{book_id}/highlights",
            params={"searchText": search_text},
        )
        return response.json()

    async def update_highlight_note(self, highlight_id: int, note: str | None) -> dict:
        """Update the note on a highlight."""
        response = await self._request(
            "POST",
            f"/api/v1/highlights/{highlight_id}/note",
            json={"note": note},
        )
        return response.json()

    async def tag_highlight(
        self, book_id: int, highlight_id: int, tag_name: str
    ) -> dict:
        """Add a tag to a highlight by name (creates tag if needed)."""
        response = await self._request(
            "POST",
            f"/api/v1/books/{book_id}/highlight/{highlight_id}/tag",
            json={"name": tag_name},
        )
        return response.json()

    async def untag_highlight(
        self, book_id: int, highlight_id: int, tag_id: int
    ) -> dict:
        """Remove a tag from a highlight."""
        response = await self._request(
            "DELETE",
            f"/api/v1/books/{book_id}/highlight/{highlight_id}/tag/{tag_id}",
        )
        return response.json()

    # --- Flashcard endpoints ---

    async def get_flashcards(self, book_id: int) -> dict:
        """Get all flashcards for a book."""
        response = await self._request("GET", f"/api/v1/books/{book_id}/flashcards")
        return response.json()

    async def create_flashcard(
        self,
        book_id: int,
        question: str,
        answer: str,
        highlight_id: int | None = None,
        chapter_id: int | None = None,
    ) -> dict:
        """Create a flashcard for a book or linked to a highlight."""
        if highlight_id is not None:
            response = await self._request(
                "POST",
                f"/api/v1/highlights/{highlight_id}/flashcards",
                json={"question": question, "answer": answer},
            )
        else:
            body: dict[str, str | int] = {"question": question, "answer": answer}
            if chapter_id is not None:
                body["chapter_id"] = chapter_id
            response = await self._request(
                "POST",
                f"/api/v1/books/{book_id}/flashcards",
                json=body,
            )
        return response.json()

    async def update_flashcard(
        self,
        flashcard_id: int,
        question: str | None = None,
        answer: str | None = None,
    ) -> dict:
        """Update a flashcard's question and/or answer."""
        body: dict[str, str] = {}
        if question is not None:
            body["question"] = question
        if answer is not None:
            body["answer"] = answer
        response = await self._request(
            "PUT", f"/api/v1/flashcards/{flashcard_id}", json=body
        )
        return response.json()

    async def delete_flashcard(self, flashcard_id: int) -> dict:
        """Delete a flashcard."""
        response = await self._request("DELETE", f"/api/v1/flashcards/{flashcard_id}")
        return response.json()

    # --- Bookmark endpoints ---

    async def get_bookmarks(self, book_id: int) -> dict:
        """Get all bookmarks for a book."""
        response = await self._request("GET", f"/api/v1/books/{book_id}/bookmarks")
        return response.json()

    async def create_bookmark(self, book_id: int, highlight_id: int) -> dict:
        """Create a bookmark for a highlight."""
        response = await self._request(
            "POST",
            f"/api/v1/books/{book_id}/bookmarks",
            json={"highlight_id": highlight_id},
        )
        return response.json()

    async def delete_bookmark(self, book_id: int, bookmark_id: int) -> dict:
        """Delete a bookmark."""
        response = await self._request(
            "DELETE", f"/api/v1/books/{book_id}/bookmarks/{bookmark_id}"
        )
        return response.json()

    # --- Highlight label endpoints ---

    async def get_book_highlight_labels(self, book_id: int) -> list:
        """Get all highlight labels for a book with resolved labels and counts."""
        response = await self._request(
            "GET", f"/api/v1/books/{book_id}/highlight-labels"
        )
        return response.json()

    async def get_global_highlight_labels(self) -> list:
        """Get all global default highlight labels."""
        response = await self._request("GET", "/api/v1/highlight-labels/global")
        return response.json()

    async def update_highlight_label(
        self, style_id: int, label: str | None = None, ui_color: str | None = None
    ) -> dict:
        """Update label text and/or UI color on a highlight style."""
        body: dict[str, str | None] = {}
        if label is not None:
            body["label"] = label
        if ui_color is not None:
            body["ui_color"] = ui_color
        response = await self._request(
            "PATCH", f"/api/v1/highlight-labels/{style_id}", json=body
        )
        return response.json()

    async def create_global_highlight_label(
        self,
        device_color: str | None = None,
        device_style: str | None = None,
        label: str | None = None,
        ui_color: str | None = None,
    ) -> dict:
        """Create a new global default highlight label."""
        body: dict[str, str | None] = {}
        if device_color is not None:
            body["device_color"] = device_color
        if device_style is not None:
            body["device_style"] = device_style
        if label is not None:
            body["label"] = label
        if ui_color is not None:
            body["ui_color"] = ui_color
        response = await self._request(
            "POST", "/api/v1/highlight-labels/global", json=body
        )
        return response.json()

    # --- Reading session endpoints ---

    async def get_reading_sessions(
        self, book_id: int, limit: int = 30, offset: int = 0
    ) -> dict:
        """Get reading sessions for a book."""
        response = await self._request(
            "GET",
            f"/api/v1/books/{book_id}/reading_sessions",
            params={"limit": limit, "offset": offset},
        )
        return response.json()

    # --- Chapter content endpoint ---

    async def get_chapter_content(self, chapter_id: int) -> dict:
        """Get the full text content of a chapter."""
        response = await self._request("GET", f"/api/v1/chapters/{chapter_id}/content")
        return response.json()

    # --- Semantic search endpoints ---

    async def semantic_search(
        self, query: str, book_id: int | None = None, limit: int = 10
    ) -> dict:
        """Search embedded content by semantic similarity, grouped by content type."""
        params: dict[str, str | int] = {"q": query, "limit": limit}
        if book_id is not None:
            params["book_id"] = book_id
        response = await self._request("GET", "/api/v1/semantic/search", params=params)
        return response.json()

    async def related_content(
        self, content_type: str, content_id: int, limit: int = 10
    ) -> dict:
        """Find content semantically similar to one already-indexed item."""
        response = await self._request(
            "GET",
            "/api/v1/semantic/related",
            params={
                "content_type": content_type,
                "content_id": content_id,
                "limit": limit,
            },
        )
        return response.json()
