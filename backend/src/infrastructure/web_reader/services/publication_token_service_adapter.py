"""Adapter wrapping the publication token service functions for DI."""

from datetime import datetime

from src.application.web_reader.dtos import PublicationToken
from src.infrastructure.web_reader.services import publication_token_service


class PublicationTokenServiceAdapter:
    """Adapter wrapping the publication token service functions for DI."""

    def create_publication_token(
        self, user_id: int, book_id: int, not_after: datetime
    ) -> PublicationToken:
        return publication_token_service.create_publication_token(user_id, book_id, not_after)
