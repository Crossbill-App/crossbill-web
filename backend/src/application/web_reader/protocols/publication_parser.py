"""Port for reading an EPUB's structure the way a Readium manifest needs it."""

from typing import Protocol

from src.application.web_reader.publications import ParsedPublication


class PublicationParserProtocol(Protocol):
    """Turns EPUB bytes into the reading order, resources and TOC a manifest lists.

    Distinct from the library's TOC parsing, which exists to attach chapters to
    stored xpointers: this one keeps the publication's own file paths, because
    the web reader has to fetch those files. One adapter implements both.
    """

    def parse_publication(self, epub_content: bytes) -> ParsedPublication:
        """Resolve an EPUB into its reading order, resources, TOC and metadata.

        Raises:
            InvalidEbookError: If the bytes are not a readable EPUB, or its
                package document is missing or unparseable.
        """
        ...
