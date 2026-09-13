"""Pointing a path inside the EPUB container at the URL this API serves it from.

A ``ParsedPublication`` names every file by its path *inside the container*
(``OEBPS/chapter1.xhtml``). A browser only knows the hrefs the manifest gave it,
which are this API's resource URLs (``resources/OEBPS/chapter1.xhtml``). The
translation lives here rather than inline in the manifest renderer because the
highlight locators and reading positions still to come cross the same boundary,
and each of them naming a file differently is exactly the bug that would surface
much later as a highlight rendering nowhere.
"""

from src.application.web_reader.anchors import Locator
from src.infrastructure.web_reader.schemas.locator_schemas import (
    LocatorLocationsSchema,
    LocatorSchema,
    LocatorTextSchema,
)

# Where the resource endpoint sits under a book's publication routes. Every
# manifest href, and so every href a browser has ever seen, starts here.
RESOURCE_PATH_PREFIX = "resources/"


def served_href(container_href: str) -> str:
    """Point a path inside the EPUB container at the URL that will serve it."""
    return f"{RESOURCE_PATH_PREFIX}{container_href}"


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
