"""The identity the KOReader plugin gives a book, and the title it computes it from."""

from src.domain.library.services.book_identity import book_title_for, koreader_client_book_id


def test_the_id_is_the_md5_of_the_title_and_the_newline_joined_authors() -> None:
    assert (
        koreader_client_book_id("The Title", ["Author One", "Author Two"])
        == "0c7953ca698ae4d46181d772610b41f4"
    )


def test_a_book_without_authors_hashes_the_title_and_an_empty_author() -> None:
    assert koreader_client_book_id("The Title", []) == "5e2b260c25dde2e059c69a884d821e19"


def test_a_single_author_is_hashed_as_is() -> None:
    assert (
        koreader_client_book_id("The Title", ["Author One"]) == "e7229b2a25a03200c4308bc81b190405"
    )


def test_the_metadata_title_wins_over_the_file_name() -> None:
    assert book_title_for("The Title", "other.epub") == "The Title"


def test_an_empty_metadata_title_falls_back_to_the_file_name() -> None:
    assert book_title_for("", "book.epub") == "book"


def test_only_the_last_extension_is_dropped_from_the_file_name() -> None:
    assert book_title_for(None, "My.Book.epub") == "My.Book"


def test_a_file_name_without_an_extension_is_used_whole() -> None:
    assert book_title_for(None, "nodot") == "nodot"


def test_a_book_with_neither_title_nor_file_name_is_untitled() -> None:
    assert book_title_for(None, None) == "Untitled"
