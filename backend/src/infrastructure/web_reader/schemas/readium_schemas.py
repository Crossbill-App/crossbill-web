"""Pydantic shapes for the `Readium Web Publication Manifest
<https://readium.org/webpub-manifest/>`_.

The manifest is JSON-LD with camelCase and ``@``-prefixed keys, none of which are
legal Python names, so every such field carries a serialization alias and the
router dumps ``by_alias=True``. Unset fields are dropped rather than serialized
as ``null``: a Readium Link with ``"properties": null`` is not the same document
as one with no properties at all.
"""

from pydantic import BaseModel, Field

WEBPUB_MEDIA_TYPE = "application/webpub+json"
WEBPUB_CONTEXT = "https://readium.org/webpub-manifest/context.jsonld"

# The profile a manifest built from an EPUB conforms to. Readium defines one URI
# per source format; this is the EPUB one, and it is what tells a navigator to
# expect EPUB semantics (a spine-shaped reading order, XHTML resources).
EPUB_PROFILE = "https://readium.org/webpub-manifest/profiles/epub"

POSITION_LIST_REL = "http://readium.org/position-list"

# The media type Readium registers for a position list, and the one its own
# toolkits both sniff for and serve. A position list is JSON, so `application/json`
# would be true as far as it goes -- it just does not tell a reader that the
# document at the other end of the link is the thing the link says it is.
POSITION_LIST_MEDIA_TYPE = "application/vnd.readium.position-list+json"


class ReadiumProperties(BaseModel):
    """A Link's ``properties``; only ``layout`` is populated today."""

    layout: str | None = None


class ReadiumLink(BaseModel):
    """A Readium Link Object.

    One shape serves the reading order, the resource list, the manifest's own
    links and the table of contents, because the spec models all four as Links.
    """

    href: str
    type: str | None = None
    rel: str | None = None
    title: str | None = None
    properties: ReadiumProperties | None = None
    children: list["ReadiumLink"] | None = None


class ReadiumMetadata(BaseModel):
    """The manifest's ``metadata`` object."""

    type: str = Field(default="http://schema.org/Book", serialization_alias="@type")
    conforms_to: str = Field(default=EPUB_PROFILE, serialization_alias="conformsTo")
    identifier: str | None = None
    title: str
    author: str | None = None
    language: str | None = None


class WebPublicationManifest(BaseModel):
    """A complete Readium Web Publication Manifest."""

    context: str = Field(default=WEBPUB_CONTEXT, serialization_alias="@context")
    metadata: ReadiumMetadata
    links: list[ReadiumLink]
    reading_order: list[ReadiumLink] = Field(serialization_alias="readingOrder")
    resources: list[ReadiumLink]
    toc: list[ReadiumLink]
