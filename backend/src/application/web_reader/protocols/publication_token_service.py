"""Protocol for the publication token service."""

from datetime import datetime
from typing import Protocol

from src.application.web_reader.dtos import PublicationToken


class PublicationTokenServiceProtocol(Protocol):
    def create_publication_token(
        self, user_id: int, book_id: int, not_after: datetime
    ) -> PublicationToken: ...
