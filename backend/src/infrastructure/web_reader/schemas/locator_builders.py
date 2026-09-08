"""Turning a derived Locator into the one a navigator in the browser can use.

A Locator computed against the EPUB names a file by its path *inside the
container* (``OEBPS/chapter1.xhtml``). A navigator only knows the hrefs the
manifest gave it, which are this API's resource URLs (``resources/OEBPS/
chapter1.xhtml``). Every locator leaving the server for a browser therefore
crosses the same boundary, and it lives here so that a second view of locators
cannot quietly translate it differently -- or forget to.
"""

from src.application.web_reader.anchors import Locator
from src.infrastructure.web_reader.schemas.reading_position_schemas import (
    LocatorLocationsSchema,
    LocatorSchema,
    LocatorTextSchema,
)

# Where the resource endpoint sits under a book's publication routes. Every
# manifest href, and so every locator href a browser has ever seen, starts here.
RESOURCE_PATH_PREFIX = "resources/"


def served_href(container_href: str) -> str:
    """Point a path inside the EPUB container at the URL that will serve it."""
    return f"{RESOURCE_PATH_PREFIX}{container_href}"


def container_href(href: str) -> str:
    """Point a URL this API serves back at the path inside the EPUB container.

    :func:`served_href` read backwards. An href carrying no such prefix is
    passed through unchanged and will simply name nothing in the publication.
    """
    return href.removeprefix(RESOURCE_PATH_PREFIX)


def served_locator_schema(locator: Locator) -> LocatorSchema:
    """Render a derived Locator in the coordinates a browser navigates by."""
    return LocatorSchema(
        href=served_href(locator.href),
        type=locator.type,
        locations=LocatorLocationsSchema(
            progression=locator.locations.progression,
            css_selector=locator.locations.css_selector,
            fragments=list(locator.locations.fragments) or None,
            position=locator.locations.position,
        ),
        text=LocatorTextSchema(
            before=locator.text.before,
            highlight=locator.text.highlight,
            after=locator.text.after,
        ),
    )
