"""Pointing a path inside the EPUB container at the URL this API serves it from.

A ``ParsedPublication`` names every file by its path *inside the container*
(``OEBPS/chapter1.xhtml``). A browser only knows the hrefs the manifest gave it,
which are this API's resource URLs (``resources/OEBPS/chapter1.xhtml``). The
translation lives here rather than inline in the manifest renderer because the
highlight locators and reading positions still to come cross the same boundary,
and each of them naming a file differently is exactly the bug that would surface
much later as a highlight rendering nowhere.
"""

from src.application.web_reader.anchors import Locator, LocatorLocations, LocatorText
from src.infrastructure.web_reader.schemas.locator_schemas import (
    LocatorLocationsSchema,
    LocatorSchema,
    LocatorTextSchema,
)
from src.infrastructure.web_reader.schemas.reading_position_schemas import (
    BrowserLocatorSchema,
)

# Where the resource endpoint sits under a book's publication routes. Every
# manifest href, and so every href a browser has ever seen, starts here.
RESOURCE_PATH_PREFIX = "resources/"


def served_href(container_href: str) -> str:
    """Point a path inside the EPUB container at the URL that will serve it."""
    return f"{RESOURCE_PATH_PREFIX}{container_href}"


def container_href(href: str) -> str:
    """Point a URL this API serves back at the path inside the EPUB container.

    :func:`served_href` read backwards. An href carrying no such prefix passes
    through unchanged, which is already a container path.
    """
    return href.removeprefix(RESOURCE_PATH_PREFIX)


def served_locator_schema(locator: Locator) -> LocatorSchema:
    """Render a derived Locator with its href pointed at the resource endpoint."""
    return LocatorSchema(
        href=served_href(locator.href),
        type=locator.type,
        locations=LocatorLocationsSchema(
            progression=locator.locations.progression,
            css_selector=locator.locations.css_selector,
        ),
        text=LocatorTextSchema(
            before=locator.text.before,
            highlight=locator.text.highlight,
            after=locator.text.after,
        ),
    )


def anchor_locator(locator: BrowserLocatorSchema) -> Locator:
    """Read a navigator's locator into the vocabulary the anchor port speaks.

    The href is the one translation that matters: every href a navigator ever saw came
    out of the manifest or the position list, so it names this endpoint's URL for a
    file rather than the file's path inside the container -- and the container path is
    what a conversion against the EPUB resolves.

    Takes the input locator of any write the browser makes, a reading position or a
    selection, since a selection is that same document with its quote required.
    """
    return Locator(
        href=container_href(locator.href),
        type=locator.type,
        locations=LocatorLocations(
            progression=locator.locations.progression,
            css_selector=locator.locations.css_selector,
            fragments=tuple(locator.locations.fragments or ()),
        ),
        text=LocatorText(
            before=locator.text.before,
            highlight=locator.text.highlight,
            after=locator.text.after,
        ),
    )
