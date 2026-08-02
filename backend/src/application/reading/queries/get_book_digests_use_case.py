"""Use case for retrieving every digest in a book."""

from src.application.library.protocols.chapter_repository import (
    ChapterRepositoryProtocol,
)
from src.application.reading.protocols.chapter_digest_repository import (
    ChapterDigestRepositoryProtocol,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.entities.chapter_digest import (
    ChapterDigest,
)
from src.domain.reading.exceptions import BookNotFoundError


class GetBookDigestsUseCase:
    """Use case for retrieving every digest in a book."""

    def __init__(
        self,
        digest_repo: ChapterDigestRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
    ) -> None:
        self.digest_repo = digest_repo
        self.chapter_repo = chapter_repo

    async def get_all_digests_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> list[ChapterDigest]:
        """Get the digest of every chapter in a book."""
        chapters = await self.chapter_repo.find_all_by_book(book_id, user_id)
        if not chapters:
            raise BookNotFoundError(book_id.value)

        return await self.digest_repo.find_all_by_book_id(book_id)
