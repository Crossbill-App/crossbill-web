"""The vocabulary the position-anchor port speaks: the Readium Locator.

An anchor is a reference to a place in a book's content. The canonical one is
the KOReader xpointer (``XPointRange``); a Locator is the Readium form of the
same anchor, derived from the xpointer and the EPUB and never authoritative.
See ``docs/adr/0004-web-reader-anchors.md``.

These dataclasses mirror the `Readium Locator
<https://readium.org/architecture/models/locators/>`_ JSON shape, minus the
fields a single EPUB resource cannot supply (``position``, ``totalProgression``,
``title``). They exist so the port speaks in application-layer terms: the
``xpoint-cfi`` library's own ``Locator`` stops at the adapter, and swapping the
library out would not change this module.
"""

from dataclasses import dataclass, field


class AnchorResolutionError(Exception):
    """A book's positions could not be converted against its EPUB.

    Raised when the bytes are not a readable EPUB, which fails every position at
    once. A single position that does not resolve is answered with ``None``
    instead: it loses a *view* of a highlight whose canonical xpointer is still
    safely stored (ADR-0004 §2).
    """


@dataclass(frozen=True)
class LocatorText:
    """A Locator's text quote: the anchored text and what surrounds it.

    Attributes:
        before: Text immediately preceding the quote in the resource.
        highlight: The quoted text; ``""`` for a caret rather than a selection.
        after: Text immediately following the quote.
    """

    before: str | None = None
    highlight: str | None = None
    after: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Serialize to the Readium JSON shape, omitting unset fields."""
        pairs = (("before", self.before), ("highlight", self.highlight), ("after", self.after))
        return {name: value for name, value in pairs if value is not None}


@dataclass(frozen=True)
class LocatorLocations:
    """A Locator's alternative expressions of the same position.

    Attributes:
        progression: Progress through the resource, 0..1. Character-based, so it
            estimates reading progress rather than rendered layout.
        css_selector: A ``querySelector``-resolvable selector for the enclosing
            element. Serialized as ``cssSelector``.
    """

    progression: float | None = None
    css_selector: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to the Readium JSON shape, omitting unset fields."""
        out: dict[str, object] = {}
        if self.progression is not None:
            out["progression"] = self.progression
        if self.css_selector is not None:
            out["cssSelector"] = self.css_selector
        return out


@dataclass(frozen=True)
class Locator:
    """The Readium form of an anchor, pointing into one resource of a book.

    Attributes:
        href: The resource's path inside the EPUB container, percent-encoded as
            a URI reference -- what a navigator resolves against the publication
            base.
        type: The resource's media type.
        locations: Alternative expressions of the position.
        text: The textual anchor.
    """

    href: str
    type: str
    locations: LocatorLocations = field(default_factory=LocatorLocations)
    text: LocatorText = field(default_factory=LocatorText)

    def to_dict(self) -> dict[str, object]:
        """Serialize to the Readium Locator JSON shape, omitting unset fields."""
        out: dict[str, object] = {"href": self.href, "type": self.type}
        if locations := self.locations.to_dict():
            out["locations"] = locations
        if text := self.text.to_dict():
            out["text"] = text
        return out
