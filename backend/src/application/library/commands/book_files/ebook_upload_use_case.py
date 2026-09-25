"""Use case for ebook upload operations."""

from src.application.common.ownership import require_book_by_client_id
from src.application.library.commands.book_files.attach_epub_use_case import AttachEpubUseCase
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.domain.common.value_objects.ids import UserId
from src.domain.library.exceptions import InvalidEbookError


class EbookUploadUseCase:
    """Attach an ebook file the KOReader plugin uploads to the book it names."""

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        attach_epub_use_case: AttachEpubUseCase,
    ) -> None:
        self.book_repository = book_repository
        self._attach_epub_use_case = attach_epub_use_case

    async def upload_ebook(
        self,
        client_book_id: str,
        content: bytes,
        content_type: str,
        user_id: int,
    ) -> None:
        """Attach the file to the user's book with this client id."""
        if content_type not in ["application/epub+zip", "application/epub"]:
            raise InvalidEbookError(
                f"Unsupported content type: {content_type}", ebook_type="UNKNOWN"
            )
        user = UserId(user_id)
        book = await require_book_by_client_id(self.book_repository, client_book_id, user)
        await self._attach_epub_use_case.attach_epub(book, content, user)
