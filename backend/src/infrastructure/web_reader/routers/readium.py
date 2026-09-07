"""API router serving the Readium Web Publication Manifest."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette import status

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationResource,
    TocEntry,
)
from src.application.web_reader.queries.get_web_publication_use_case import (
    GetWebPublicationUseCase,
)
from src.core import container
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity import get_current_user
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
    current_user: Annotated[User, Depends(get_current_user)],
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
