"""Query adapter serving one file out of a book's stored publication index and EPUB."""

import asyncio
import zipfile
from io import BytesIO
from urllib.parse import unquote

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.publications import ParsedPublication
from src.application.web_reader.queries.publication_resource import PublicationResourceView
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.exceptions import EbookFileNotFoundError, InvalidEbookError
from src.domain.web_reader.exceptions import PublicationResourceNotFoundError
from src.infrastructure.common.zip_members import read_bounded_member
from src.infrastructure.web_reader.mappers.publication_json import publication_from_json
from src.infrastructure.web_reader.publication_rows import publication_row


class PublicationResourceQuery:
    """Serves one file of a book's publication, byte-for-byte as the EPUB holds it."""

    def __init__(self, db: AsyncSession, file_repository: FileRepositoryProtocol) -> None:
        self.db = db
        self.file_repository = file_repository

    async def get_publication_resource(
        self, book_id: BookId, user_id: UserId, path: str, known_versions: frozenset[str] | None
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when no index is stored."""
        result = await self.db.execute(publication_row(book_id, user_id))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None

        publication = publication_from_json(orm.publication, orm.content_hash)
        media_type = _media_types(publication).get(path)
        # Membership is checked first so that a path the publication does not
        # list is a 404 rather than a 304: a precondition narrows a request that
        # would otherwise succeed (RFC 9110 §13.2), never turns a refusal into
        # "your copy is current".
        if media_type is None:
            raise PublicationResourceNotFoundError(path)

        version = publication.content_hash
        if known_versions is None or version in known_versions:
            return PublicationResourceView(media_type=media_type, content=None, version=version)

        content = await self.file_repository.get_epub(orm.file_name)
        if content is None:
            raise EbookFileNotFoundError(book_id.value)

        member = await asyncio.to_thread(_read_member, content, path)
        return PublicationResourceView(media_type=media_type, content=member, version=version)


def _media_types(publication: ParsedPublication) -> dict[str, str]:
    """Map each file the publication offers to the media type declared for it.

    Membership here is the whole access rule: the package document, ``META-INF/``
    and any path climbing out of the container are absent from these two lists
    and so need no separate traversal guard. Decoding an href exactly once
    matches what ASGI already did to the URL path.
    """
    return {
        unquote(resource.href): resource.media_type
        for resource in (*publication.reading_order, *publication.resources)
    }


def _read_member(content: bytes, path: str) -> bytes:
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except (OSError, zipfile.BadZipFile) as e:
        raise InvalidEbookError(f"stored archive cannot be opened: {e!s}", "epub") from e
    with archive:
        try:
            entry = archive.getinfo(path)
        except KeyError:
            # The index is derived from the package document rather than from
            # the archive's file list, so a manifest may name a member the
            # container does not hold.
            raise PublicationResourceNotFoundError(path) from None
        return read_bounded_member(archive, entry)
