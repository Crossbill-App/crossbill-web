"""The identity the KOReader plugin gives a book, computed from its metadata alone."""

import hashlib
from collections.abc import Sequence


def koreader_client_book_id(title: str, authors: Sequence[str]) -> str:
    """The ``client_book_id`` the KOReader plugin would send for this book.

    Reproduces the plugin's ``md5("title|author")``, so a book imported on the web
    is the book the plugin later syncs into.
    """
    # crengine's author is every dc:creator joined by a newline; the title goes in
    # as-is, since whether crengine trims it is unconfirmed.
    author = "\n".join(authors)
    return hashlib.md5(f"{title}|{author}".encode(), usedforsecurity=False).hexdigest()


def book_title_for(metadata_title: str | None, file_name: str | None) -> str:
    """The title a book goes by: its metadata's, else its file's name, else ``Untitled``."""
    if metadata_title:
        return metadata_title
    if file_name:
        # KOReader's own fallback: the file name up to its last dot.
        return file_name.rpartition(".")[0] or file_name
    return "Untitled"
