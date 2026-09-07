"""The vocabulary the position-anchor port speaks: Locators, matches, confidence.

An Anchor is a reference to a place in a book's content. The stored, canonical
anchor is the KOReader xpointer (``XPointRange``); a Locator is the Readium form
of the same anchor, derived from the xpointer and the EPUB and never
authoritative. See ``docs/adr/0004-web-reader-anchors.md``.

These dataclasses mirror the `Readium Locator
<https://readium.org/architecture/models/locators/>`_ JSON shape, minus the
fields a single EPUB resource cannot supply (``position``, ``totalProgression``,
``title``). They exist so the port speaks in application-layer terms: the
``xpoint-cfi`` library's own ``Locator`` and ``MatchConfidence`` stop at the
adapter, and swapping the library out would not change this module.

``to_dict()`` emits the camelCase Readium keys, so a router can hand the result
straight to a Pydantic schema without a second translation.
"""

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum

from src.domain.common.value_objects.xpoint import XPointRange


class AnchorResolutionError(Exception):
    """A position could not be converted against the book's EPUB.

    Raised when the xpointer does not resolve, the locator names no resource, or
    the EPUB is missing or unreadable. A derivation failure loses a *view* of a
    highlight whose canonical xpointer is still safely stored, so callers are
    expected to catch this and degrade the anchor rather than fail the request.
    """


class AnchorConfidence(IntEnum):
    """How much evidence backed a locator-to-xpointer match, weakest first.

    Resolving a Locator back to an xpointer is a text search, not a lookup, so it
    comes with a grade. The members are ordered, which is the point: a caller
    sets a floor (``if match.confidence < AnchorConfidence.ONE_CONTEXT: reject``)
    instead of enumerating cases.

    Attributes:
        FUZZY: The quote was not found verbatim; offsets come from the best
            approximate window and may be off by a few characters.
        AMBIGUOUS: The quote occurs several times and neither context settled
            which one.
        HIGHLIGHT_ONLY: The quote occurs exactly once, with no context to confirm
            it.
        ONE_CONTEXT: The quote matched with either ``before`` or ``after``
            abutting it.
        BOTH_CONTEXTS: The quote matched with both contexts abutting it -- what a
            locator derived from the same EPUB should always come back as.
    """

    FUZZY = 0
    AMBIGUOUS = 1
    HIGHLIGHT_ONLY = 2
    ONE_CONTEXT = 3
    BOTH_CONTEXTS = 4


class AnchorSource(StrEnum):
    """What a Locator gave the conversion to find a position by.

    A Locator produced from a *selection* carries a text quote, which is the
    evidence :class:`AnchorConfidence` grades. A Locator produced from a
    *reading position* frequently carries none: ``@readium/navigator`` reports a
    page turn from its snapper's ``progress`` event, and the Locator it builds
    from that has an ``href`` and a progression and nothing else. Those points
    are still resolvable, from weaker evidence, and a caller has to be able to
    tell which kind it got -- the two are not comparable on one scale.

    Attributes:
        QUOTE: The Locator carried text, and the position is where that text
            was found. This is the only kind whose ``AnchorConfidence`` grades
            evidence the *caller* supplied.
        ELEMENT: The Locator named one element -- a CSS selector or a fragment
            id -- and the position is where that element's text begins.
            Precision is an element: exactly one place, corroborated by nothing
            beyond the element's own identity.
        PROGRESSION: The Locator said only how far through the resource it was,
            and the position is that fraction of the resource's text. Precision
            is approximate by construction, because a fraction of the rendered
            layout is not a fraction of the character count.
    """

    QUOTE = "quote"
    ELEMENT = "element"
    PROGRESSION = "progression"


@dataclass(frozen=True)
class LocatorText:
    """A Locator's text quote: the highlighted text and what surrounds it.

    Attributes:
        before: Text immediately preceding the quote in the resource.
        highlight: The quoted text; ``""`` for a single position rather than a
            selection.
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
        fragments: Fragment identifiers the position sits on, most specific
            first, as a navigator reports them (``"#chapter-two"``). Carried
            because they name an element exactly, which is the second-best thing
            to a quote when a reading position arrives without one.
    """

    progression: float | None = None
    css_selector: str | None = None
    fragments: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialize to the Readium JSON shape, omitting unset fields."""
        out: dict[str, object] = {}
        if self.progression is not None:
            out["progression"] = self.progression
        if self.css_selector is not None:
            out["cssSelector"] = self.css_selector
        if self.fragments:
            out["fragments"] = list(self.fragments)
        return out


@dataclass(frozen=True)
class Locator:
    """The Readium form of an Anchor, pointing into one resource of a book.

    Attributes:
        href: The resource's path inside the EPUB container, percent-encoded as a
            URI reference -- what a navigator resolves against the publication
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


@dataclass(frozen=True)
class AnchorMatch:
    """The outcome of resolving a Locator back to canonical KOReader coordinates.

    Attributes:
        xpoints: The range the Locator's quote was found at -- the thing that
            would be stored, if the caller trusts the confidence.
        confidence: How much evidence backed the match, on the scale its
            ``anchored_by`` supports. A point resolved from an element or a
            progression is capped below what a quote can reach, because the
            evidence behind it is weaker in kind and not only in degree.
        anchored_by: What the Locator gave the conversion to work from. A floor
            is only meaningful against this: ``BOTH_CONTEXTS`` from a quote and
            ``FUZZY`` from a progression are not two points on one scale.
    """

    xpoints: XPointRange
    confidence: AnchorConfidence
    anchored_by: AnchorSource = AnchorSource.QUOTE
