"""API router serving a book's Readium Web Publication Manifest, position list and files."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from starlette import status

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationResource,
    TocEntry,
)
from src.application.web_reader.queries.get_publication_positions_use_case import (
    GetPublicationPositionsUseCase,
)
from src.application.web_reader.queries.get_publication_resource_use_case import (
    GetPublicationResourceUseCase,
)
from src.application.web_reader.queries.get_publication_use_case import GetPublicationUseCase
from src.application.web_reader.queries.publication_positions import PublicationPosition
from src.config import get_settings
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
from src.infrastructure.web_reader.schemas.locator_builders import served_href
from src.infrastructure.web_reader.schemas.readium_schemas import (
    POSITION_LIST_MEDIA_TYPE,
    POSITION_LIST_REL,
    WEBPUB_MEDIA_TYPE,
    PositionList,
    ReadiumLink,
    ReadiumLocations,
    ReadiumLocator,
    ReadiumMetadata,
    ReadiumProperties,
    WebPublicationManifest,
)

router = APIRouter(prefix="/readium", tags=["readium"])

# Every href in the manifest is relative to the manifest's own URL, so a reader
# that has resolved `/readium/books/7/manifest.json` reaches the position list at
# `/readium/books/7/positions.json` with no base URL to configure.
POSITION_LIST_HREF = "positions.json"

# A table-of-contents heading that links nowhere. A Readium Link must have an
# href, so the entry keeps its title and points at the manifest itself.
UNLINKED_TOC_HREF = "#"

# A publication is one user's book, so a shared cache must not hold it.
RESOURCE_CACHE_CONTROL = "private"

# Readium reads a resource with `fetch()` and frames a blob it builds from the
# text, so this header never reaches the path the reader takes. A browser
# navigating straight at the URL gets same-origin markup the user uploaded, and
# `sandbox` with no tokens leaves that document an opaque origin with no
# scripts, no forms and no top-level navigation.
RESOURCE_CONTENT_SECURITY_POLICY = "sandbox"

# A plain `type/subtype`, no parameters, and deliberately narrower than RFC 9110
# §8.3.1's `token` -- which an EPUB's package document has no use for.
_MEDIA_TYPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*")
FALLBACK_MEDIA_TYPE = "application/octet-stream"

# An entity-tag as RFC 9110 §8.8.3 spells one: an optionally `W/`-prefixed
# quoted string, whose content is any visible character but the quote itself.
# The comparison for a GET is weak, so the prefix is read and discarded.
_ENTITY_TAG = re.compile(r'(?:W/)?"(?P<version>[\x21\x23-\x7e]*)"')


class WebpubJSONResponse(JSONResponse):
    """JSON served as ``application/webpub+json``, which is what a navigator looks for."""

    media_type = WEBPUB_MEDIA_TYPE


class PositionListJSONResponse(JSONResponse):
    """A position list served as the media type Readium registers for one."""

    media_type = POSITION_LIST_MEDIA_TYPE


@router.get(
    "/books/{book_id}/manifest.json",
    response_model=WebPublicationManifest,
    response_class=WebpubJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_readium_manifest(
    book_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetPublicationUseCase = Depends(
        inject_use_case(container.web_reader.get_publication_use_case)
    ),
) -> WebpubJSONResponse:
    """Get the Readium Web Publication Manifest for a book's EPUB."""
    publication = await use_case.get_publication(
        book_id=book_id,
        user_id=current_user.id.value,
    )
    manifest = _manifest(publication, self_href=_self_href(request))
    return WebpubJSONResponse(
        content=manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
    )


@router.get(
    "/books/{book_id}/positions.json",
    response_model=PositionList,
    response_class=PositionListJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_readium_positions(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetPublicationPositionsUseCase = Depends(
        inject_use_case(container.web_reader.get_publication_positions_use_case)
    ),
) -> PositionListJSONResponse:
    """Get the Readium position list for a book's EPUB.

    This is what the manifest's ``position-list`` link resolves to: one Locator
    per synthetic page of the publication, which is how a reader turns "where am
    I" into a number it can show and store.
    """
    positions = await use_case.get_publication_positions(
        book_id=book_id,
        user_id=current_user.id.value,
    )
    document = PositionList(
        total=len(positions),
        positions=[_locator(position) for position in positions],
    )
    return PositionListJSONResponse(
        content=document.model_dump(mode="json", by_alias=True, exclude_none=True)
    )


@router.get(
    "/books/{book_id}/resources/{path:path}",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "content": {"*/*": {"schema": {"type": "string", "format": "binary"}}},
            "description": "The file, under the media type the publication declares for it.",
        },
        status.HTTP_304_NOT_MODIFIED: {"description": "The caller already holds this version."},
    },
)
async def get_readium_resource(
    book_id: int,
    path: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetPublicationResourceUseCase = Depends(
        inject_use_case(container.web_reader.get_publication_resource_use_case)
    ),
) -> Response:
    """Get one file of a book's publication, unchanged.

    ``path`` is a manifest href with the ``resources/`` prefix stripped and
    decoded once by ASGI, which is the archive member's own name. Only the files
    the manifest names are reachable.
    """
    resource = await use_case.get_publication_resource(
        book_id=book_id,
        user_id=current_user.id.value,
        path=path,
        known_versions=_known_versions(request.headers.get("if-none-match")),
    )
    # A 304 updates the headers of the copy a cache already holds (RFC 9111
    # §4.3.4), so a policy left off one is a policy revalidation strips from a
    # stored response.
    headers = {
        "ETag": f'"{resource.version}"',
        "Cache-Control": RESOURCE_CACHE_CONTROL,
        "Content-Security-Policy": RESOURCE_CONTENT_SECURITY_POLICY,
    }
    if resource.content is None:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    # Content-Type is a raw header rather than `media_type`, which would append
    # `; charset=utf-8` to every `text/*` type. The bytes go out unchanged and an
    # EPUB's documents declare their own encoding.
    content_type = _servable_media_type(resource.media_type)
    return Response(content=resource.content, headers=headers | {"Content-Type": content_type})


def _known_versions(if_none_match: str | None) -> frozenset[str] | None:
    """Read the versions a caller says it already holds out of ``If-None-Match``.

    ``None`` is the wildcard, and is deliberately not a version: ``*`` is a
    legal entity-tag character, so a sentinel inside the set would make the
    quoted tag ``"*"`` indistinguishable from it.

    Anything that is not an entity-tag (RFC 9110 §8.8.3) is dropped rather than
    repaired: answering 304 to a validator the standard does not define tells a
    reader its copy is current on no authority, where serving the file does not.
    """
    if not if_none_match:
        return frozenset()
    # `*` stands for any current representation (RFC 9110 §13.1.2), and only on
    # its own -- mixed with tags it is not a header the grammar defines.
    if if_none_match.strip() == "*":
        return None
    parsed = (_ENTITY_TAG.fullmatch(tag.strip()) for tag in if_none_match.split(","))
    return frozenset(tag.group("version") for tag in parsed if tag is not None)


def _servable_media_type(declared: str) -> str:
    """Keep a package document's media type out of the response unless it is one.

    The value is copied from a file the user uploaded: one carrying a newline
    would smuggle a second header, one outside Latin-1 would fail to encode.
    """
    return declared if _MEDIA_TYPE.fullmatch(declared) else FALLBACK_MEDIA_TYPE


def _self_href(request: Request) -> str:
    """Where this manifest says it lives -- the URL everything else resolves against.

    ``PUBLIC_BASE_URL`` is required in production, where ``request.url`` names
    only the hop that reached this process. It is empty everywhere else, and
    there the request's own URL is the honest answer.
    """
    base = get_settings().PUBLIC_BASE_URL
    return f"{base}{request.url.path}" if base else str(request.url)


def _manifest(publication: ParsedPublication, self_href: str) -> WebPublicationManifest:
    """Render a parsed publication as a manifest served from ``self_href``."""
    metadata = publication.metadata
    return WebPublicationManifest(
        metadata=ReadiumMetadata(
            identifier=metadata.identifier,
            # Unreachable: the use case has already substituted the book's title
            # for a publication that states none, and a Book cannot have an empty
            # one. The `or` is what carries `str | None` into a required `str`.
            title=metadata.title or "",
            author=metadata.author,
            language=metadata.language,
        ),
        links=[
            ReadiumLink(href=self_href, rel="self", type=WEBPUB_MEDIA_TYPE),
            ReadiumLink(
                href=POSITION_LIST_HREF,
                rel=POSITION_LIST_REL,
                type=POSITION_LIST_MEDIA_TYPE,
            ),
        ],
        reading_order=[_resource_link(item) for item in publication.reading_order],
        resources=[_resource_link(item) for item in publication.resources],
        toc=[_toc_link(entry) for entry in publication.toc],
    )


def _locator(position: PublicationPosition) -> ReadiumLocator:
    """Render one computed position as a Locator pointing at the resource endpoint."""
    return ReadiumLocator(
        href=served_href(position.href),
        type=position.media_type,
        locations=ReadiumLocations(
            position=position.position,
            progression=position.progression,
            total_progression=position.total_progression,
        ),
    )


def _resource_link(resource: PublicationResource) -> ReadiumLink:
    """Render one publication file as a Link pointing at the resource endpoint."""
    layout = resource.layout
    return ReadiumLink(
        href=served_href(resource.href),
        type=resource.media_type,
        properties=ReadiumProperties(layout=layout.value) if layout else None,
    )


def _toc_link(entry: TocEntry) -> ReadiumLink:
    """Render one table-of-contents entry, and everything nested under it."""
    children = [_toc_link(child) for child in entry.children]
    return ReadiumLink(
        href=served_href(entry.href) if entry.href else UNLINKED_TOC_HREF,
        title=entry.title,
        children=children or None,
    )
