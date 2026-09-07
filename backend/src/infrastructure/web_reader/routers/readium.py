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
from src.application.web_reader.queries.publication_resource import ANY_VERSION
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

# An entity-tag as RFC 9110 §8.8.3 spells one: an optionally `W/`-prefixed
# quoted string, whose content is any visible character but the quote itself.
_ENTITY_TAG = re.compile(r'(?:W/)?"(?P<version>[\x21\x23-\x7e]*)"')


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
        known_versions=_known_versions(request.headers.get("if-none-match")),
    )
    headers = {
        "ETag": f'"{resource.version}"',
        "Cache-Control": RESOURCE_CACHE_CONTROL,
    }
    # No content means the caller's copy is current -- and, because it was asked
    # up front, means the file was never decompressed to find that out.
    if resource.content is None:
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


def _known_versions(if_none_match: str | None) -> frozenset[str]:
    """Read the versions a caller says it already holds out of ``If-None-Match``.

    They are handed to the read, rather than compared against what comes back,
    so that a file the caller already has is never decompressed to answer that
    it has it.

    ``*`` stands for any current representation (RFC 9110 §13.1.2), and only on
    its own -- mixed with tags it is not a header the grammar defines.

    Everything else is read as the grammar spells it (§8.8.3): an entity-tag is
    a quoted string, optionally prefixed ``W/``, and the comparison for a GET is
    weak, so ``W/"x"`` and ``"x"`` name the same version. Anything that is not
    an entity-tag is dropped rather than repaired -- unwrapping optional quotes
    would let a bare token match, and answering 304 to a validator the standard
    does not define means telling a reader its copy is current on no authority.
    Dropping it serves the file, which is the harmless way to be unsure.

    A tag may itself contain a comma, which splitting cannot honour; such a tag
    matches nothing and the file is served. Ours are hexadecimal, so this costs
    a revalidation only to a client echoing a tag it did not get from here.
    """
    if not if_none_match:
        return frozenset()
    if if_none_match.strip() == ANY_VERSION:
        return frozenset({ANY_VERSION})
    parsed = (_ENTITY_TAG.fullmatch(tag.strip()) for tag in if_none_match.split(","))
    return frozenset(tag.group("version") for tag in parsed if tag is not None)


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
