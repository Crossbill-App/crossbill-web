"""API router serving the Readium Web Publication Manifest and the files it names."""

import re

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from starlette import status

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationResource,
    TocEntry,
)
from src.application.web_reader.queries.get_publication_resource_use_case import (
    GetPublicationResourceUseCase,
)
from src.application.web_reader.queries.get_web_publication_use_case import (
    GetWebPublicationUseCase,
)
from src.core import container
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.web_reader.dependencies import PublicationReader
from src.infrastructure.web_reader.schemas.readium_schemas import (
    POSITION_LIST_REL,
    WEBPUB_MEDIA_TYPE,
    ReadiumLink,
    ReadiumMetadata,
    ReadiumProperties,
    WebPublicationManifest,
)

router = APIRouter(prefix="/readium", tags=["readium"])

# Every href in the manifest is relative to the manifest's own URL, so a reader
# that has resolved `/readium/books/7/manifest.json` reaches a resource at
# `/readium/books/7/resources/<path in the container>` and the position list at
# `/readium/books/7/positions.json`, with no base URL to configure. The two
# endpoints those point at arrive in M1.2 and M1.3; linking to them now is what
# the manifest is for.
RESOURCE_PATH_PREFIX = "resources/"
POSITION_LIST_HREF = "positions.json"

# A table-of-contents heading that links nowhere. A Readium Link must have an
# href, so the entry keeps its title and points at the manifest itself.
UNLINKED_TOC_HREF = "#"

# A publication is one user's book, so a shared cache must not hold it. Within
# the browser's own cache the entity tag does the revalidating, and there is no
# max-age: a book's file can be replaced under it at any time.
RESOURCE_CACHE_CONTROL = "private"

# A media type as RFC 9110 §8.3.1 writes one, with no parameters, which is all
# an EPUB's package document ever declares.
_MEDIA_TYPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*")
FALLBACK_MEDIA_TYPE = "application/octet-stream"


class WebpubJSONResponse(JSONResponse):
    """JSON served as ``application/webpub+json``, which is what a navigator looks for."""

    media_type = WEBPUB_MEDIA_TYPE


@router.get(
    "/books/{book_id}/manifest.json",
    response_model=WebPublicationManifest,
    response_class=WebpubJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_readium_manifest(
    book_id: int,
    request: Request,
    current_user: PublicationReader,
    use_case: GetWebPublicationUseCase = Depends(
        inject_use_case(container.web_reader.get_web_publication_use_case)
    ),
) -> WebpubJSONResponse:
    """Get the Readium Web Publication Manifest for a book's EPUB."""
    publication = await use_case.get_web_publication(
        book_id=book_id,
        user_id=current_user.id.value,
    )
    manifest = _manifest(publication, self_href=str(request.url))
    return WebpubJSONResponse(
        content=manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
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
    current_user: PublicationReader,
    use_case: GetPublicationResourceUseCase = Depends(
        inject_use_case(container.web_reader.get_publication_resource_use_case)
    ),
) -> Response:
    """Get one file of a book's publication, unchanged.

    ``path`` is a manifest href with the ``resources/`` prefix stripped, so it
    arrives here as the container-root path the reading order or the resource
    list published -- decoded once by ASGI, which is the archive member's own
    name. Only the files the manifest names are reachable; the package document
    and ``META-INF/`` are not part of the publication and answer 404 like any
    other path the manifest does not list.
    """
    resource = await use_case.get_publication_resource(
        book_id=book_id,
        user_id=current_user.id.value,
        path=path,
    )
    etag = f'"{resource.version}"'
    headers = {"ETag": etag, "Cache-Control": RESOURCE_CACHE_CONTROL}
    if _already_holds(request.headers.get("if-none-match"), etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    # Content-Type goes in the headers rather than through `media_type`, which
    # would append `; charset=utf-8` to every `text/*` type. The bytes are
    # served unchanged and an EPUB's documents declare their own encoding, so
    # the type the package document stated is the honest one to send.
    #
    # The whole file is read rather than streamed. Its bytes are already in
    # memory -- the EPUB was loaded whole to be parsed at all -- so streaming
    # would add chunking around a buffer that exists either way, and would only
    # start paying off once resources are served without parsing the
    # publication first (#745).
    content_type = _servable_media_type(resource.media_type)
    return Response(content=resource.content, headers=headers | {"Content-Type": content_type})


def _servable_media_type(declared: str) -> str:
    """Keep a package document's media type out of the response unless it is one.

    The type is copied from a file the user uploaded, so it reaches here as
    arbitrary text. Anything but a plain ``type/subtype`` is replaced rather
    than echoed: a value carrying a newline would smuggle a second header into
    the response, and one carrying a character outside Latin-1 would fail to
    encode at all. A publication that mislabels a file this way still serves,
    under the type a browser will not act on.
    """
    return declared if _MEDIA_TYPE.fullmatch(declared) else FALLBACK_MEDIA_TYPE


def _already_holds(if_none_match: str | None, etag: str) -> bool:
    """Decide whether a conditional request may be answered with 304.

    RFC 9110 §13.1.2: ``*`` matches any current representation, and a list of
    tags is compared weakly, so ``W/"x"`` and ``"x"`` are the same version of
    the same file.
    """
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    return any(_strong(tag.strip()) == _strong(etag) for tag in if_none_match.split(","))


def _strong(entity_tag: str) -> str:
    """Drop a weak validator's prefix, leaving the tag itself."""
    return entity_tag.removeprefix("W/")


def _manifest(publication: ParsedPublication, self_href: str) -> WebPublicationManifest:
    """Render a parsed publication as a manifest served from ``self_href``."""
    metadata = publication.metadata
    return WebPublicationManifest(
        metadata=ReadiumMetadata(
            identifier=metadata.identifier,
            title=metadata.title or "",
            author=metadata.author,
            language=metadata.language,
        ),
        links=[
            ReadiumLink(href=self_href, rel="self", type=WEBPUB_MEDIA_TYPE),
            ReadiumLink(
                href=POSITION_LIST_HREF,
                rel=POSITION_LIST_REL,
                type="application/json",
            ),
        ],
        reading_order=[_resource_link(item) for item in publication.reading_order],
        resources=[_resource_link(item) for item in publication.resources],
        toc=[_toc_link(entry) for entry in publication.toc],
    )


def _resource_link(resource: PublicationResource) -> ReadiumLink:
    """Render one publication file as a Link pointing at the resource endpoint."""
    layout = resource.layout
    return ReadiumLink(
        href=_served_href(resource.href),
        type=resource.media_type,
        properties=ReadiumProperties(layout=layout.value) if layout else None,
    )


def _toc_link(entry: TocEntry) -> ReadiumLink:
    """Render one table-of-contents entry, and everything nested under it."""
    children = [_toc_link(child) for child in entry.children]
    return ReadiumLink(
        href=_served_href(entry.href) if entry.href else UNLINKED_TOC_HREF,
        title=entry.title,
        children=children or None,
    )


def _served_href(container_href: str) -> str:
    """Point a path inside the EPUB container at the URL that will serve it."""
    return f"{RESOURCE_PATH_PREFIX}{container_href}"
