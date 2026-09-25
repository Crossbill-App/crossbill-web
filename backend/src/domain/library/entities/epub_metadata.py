from dataclasses import dataclass


@dataclass(frozen=True)
class EpubMetadata:
    """The Dublin Core fields an EPUB's package document names its book by."""

    title: str | None
    authors: tuple[str, ...]
    language: str | None
