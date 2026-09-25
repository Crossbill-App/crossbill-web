from typing import Protocol

from src.domain.library.entities.chapter import TocChapter
from src.domain.library.entities.epub_metadata import EpubMetadata


class EpubParserProtocol(Protocol):
    def parse_toc(self, epub_content: bytes) -> list[TocChapter]: ...

    def validate_epub(self, content: bytes) -> bool: ...

    def extract_cover(self, epub_content: bytes) -> bytes | None: ...

    def extract_metadata(self, content: bytes) -> EpubMetadata: ...
