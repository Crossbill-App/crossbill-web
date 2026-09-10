"""The stored form of a ``ParsedPublication``: how the index is written to JSON and read back.

Every key is spelled out here rather than taken from a dataclass field name,
because these rows outlive the code that wrote them: renaming a field must break
this module loudly instead of silently invalidating stored publications.

``content_hash`` is deliberately absent from the payload -- it lives in its own
column, which is the single source, and is handed back in on load.
"""

from typing import Any

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationLayout,
    PublicationMetadata,
    PublicationResource,
    TocEntry,
)


def publication_to_json(publication: ParsedPublication) -> dict[str, Any]:
    """Render a parsed publication as the JSON document stored beside the book."""
    return {
        "metadata": _metadata_to_json(publication.metadata),
        "reading_order": [_resource_to_json(item) for item in publication.reading_order],
        "resources": [_resource_to_json(item) for item in publication.resources],
        "toc": [_toc_entry_to_json(entry) for entry in publication.toc],
    }


def publication_from_json(payload: dict[str, Any], content_hash: str) -> ParsedPublication:
    """Rebuild a parsed publication from its stored JSON and the hash column beside it."""
    return ParsedPublication(
        metadata=_metadata_from_json(payload["metadata"]),
        reading_order=tuple(_resource_from_json(item) for item in payload["reading_order"]),
        resources=tuple(_resource_from_json(item) for item in payload["resources"]),
        toc=tuple(_toc_entry_from_json(entry) for entry in payload["toc"]),
        content_hash=content_hash,
    )


def _metadata_to_json(metadata: PublicationMetadata) -> dict[str, Any]:
    return {
        "title": metadata.title,
        "author": metadata.author,
        "language": metadata.language,
        "identifier": metadata.identifier,
    }


def _metadata_from_json(payload: dict[str, Any]) -> PublicationMetadata:
    return PublicationMetadata(
        title=payload["title"],
        author=payload["author"],
        language=payload["language"],
        identifier=payload["identifier"],
    )


def _resource_to_json(resource: PublicationResource) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "href": resource.href,
        "media_type": resource.media_type,
        "size": resource.size,
    }
    # A resource stating no layout carries no key, mirroring the manifest, where
    # an absent ``layout`` is what lets a reader apply its own.
    if resource.layout is not None:
        payload["layout"] = resource.layout.value
    return payload


def _resource_from_json(payload: dict[str, Any]) -> PublicationResource:
    layout = payload.get("layout")
    return PublicationResource(
        href=payload["href"],
        media_type=payload["media_type"],
        size=payload["size"],
        layout=PublicationLayout(layout) if layout is not None else None,
    )


def _toc_entry_to_json(entry: TocEntry) -> dict[str, Any]:
    return {
        "title": entry.title,
        "href": entry.href,
        "children": [_toc_entry_to_json(child) for child in entry.children],
    }


def _toc_entry_from_json(payload: dict[str, Any]) -> TocEntry:
    return TocEntry(
        title=payload["title"],
        href=payload["href"],
        children=tuple(_toc_entry_from_json(child) for child in payload["children"]),
    )
