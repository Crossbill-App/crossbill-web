"""The counting rule behind a resolved xpoint's character offset.

A text node counts its characters with each whitespace run as one. Images,
empty markup, whitespace between tags, scripts, styles and the head count zero,
and so does anything in the spine that is not a document.
"""

from src.domain.common.value_objects.position_index import PositionIndex
from src.infrastructure.library.services.epub_position_index_service import (
    EpubPositionIndexService,
)
from tests.epub_builders import build_epub, container_xml

# ebooklib only finds a package document whose rootfile states its media type.
CONTAINER = container_xml(
    '<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
)


def index_of_spine(*items: tuple[str, str, str]) -> PositionIndex:
    """Index a book whose spine holds these ``(name, media type, content)`` items, in order."""
    content = build_epub(
        "".join(
            f'<item id="i{n}" href="{name}" media-type="{media_type}"/>'
            for n, (name, media_type, _) in enumerate(items, start=1)
        ),
        "".join(f'<itemref idref="i{n}"/>' for n in range(1, len(items) + 1)),
        documents={name: document for name, _, document in items},
        container=CONTAINER,
    )
    return EpubPositionIndexService().build_position_index(content)


def index_of(*bodies: str) -> PositionIndex:
    """Index a book whose spine holds one XHTML document per body, in order."""
    return index_of_spine(
        *(
            (
                f"doc{n}.xhtml",
                "application/xhtml+xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<html xmlns="http://www.w3.org/1999/xhtml"><body>{body}</body></html>',
            )
            for n, body in enumerate(bodies, start=1)
        )
    )


def test_a_whitespace_run_counts_as_one_character() -> None:
    index = index_of("<p>one \n\t  two</p><p>\n  three  </p><p>four</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p[2]") == 7
    assert index.character_offset("/body/DocFragment[1]/body/p[3]") == 14
    assert index.total_characters == 18


def test_images_empty_markup_and_whitespace_between_tags_count_zero() -> None:
    index = index_of('<p>ab</p>\n  <img src="x.png"/>\n  <div><span></span></div>\n  <p>cd</p>')

    assert index.character_offset("/body/DocFragment[1]/body/img.0") == 2
    assert index.character_offset("/body/DocFragment[1]/body/p[2]/text().1") == 3
    assert index.total_characters == 4


def test_scripts_and_styles_count_zero() -> None:
    index = index_of("<p>ab</p><script>let x = 1;</script><style>p {}</style><p>cd</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p[2]/text().0") == 2
    assert index.total_characters == 4


def test_the_head_of_an_html_document_counts_zero() -> None:
    # ebooklib empties the head of XHTML documents only; text/html keeps its own
    index = index_of_spine(
        (
            "doc.html",
            "text/html",
            "<html><head><title>Title</title></head><body><p>ab</p></body></html>",
        )
    )

    assert index.character_offset("/body/DocFragment[1]/body/p/text().0") == 0
    assert index.total_characters == 2


def test_an_image_in_the_spine_counts_zero() -> None:
    index = index_of_spine(
        ("cover.png", "image/png", "\x89PNG\r\n\x1a\n\x00\x00 not text"),
        ("doc.html", "text/html", "<html><body><p>ab</p></body></html>"),
    )

    assert index.character_offset("/body/DocFragment[2]/body/p/text().1") == 1
    assert index.total_characters == 2


def test_a_comment_splits_its_parents_text_nodes() -> None:
    index = index_of("<p>ab<!-- note -->cd</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p/text()[2].1") == 3


def test_an_xpoint_in_a_later_text_node_counts_the_nodes_before_it() -> None:
    index = index_of("<p>She wrote <em>the same sentence</em> twice.</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p/text()[2].3") == 30
    assert index.character_offset("/body/DocFragment[1]/body/p/em/text().4") == 14


def test_an_element_xpoint_starts_before_its_first_child() -> None:
    index = index_of("<p>ab</p><p><em>cd</em> ef</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p[2]") == 2
    assert index.character_offset("/body/DocFragment[1]/body/p[2]/text().0") == 4


def test_an_offset_past_its_text_is_clamped_to_it() -> None:
    index = index_of("<p>abc <em>de</em> fg</p><p>hi</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p[1]/text().99") == 4
    assert index.character_offset("/body/DocFragment[1]/body/p[1]/text()[9].1") == 1
    assert index.character_offset("/body/DocFragment[1]/body/p[1].99") == 9


def test_offsets_run_on_across_spine_documents() -> None:
    index = index_of("<p>abc</p>", "<p>de</p>")

    assert index.character_offset("/body/DocFragment[2]/body/p/text().1") == 4
    assert index.total_characters == 5


def test_an_xpoint_the_book_lacks_has_no_offset() -> None:
    index = index_of("<p>abc</p>")

    assert index.character_offset("/body/DocFragment[2]/body/p/text().1") is None
    assert index.character_offset("not an xpoint") is None


def test_a_blocks_leading_whitespace_is_not_a_text_node() -> None:
    # crengine drops it, so KOReader numbers the text after <em> as text()[1]
    index = index_of("<p>\n  <em>a</em>bc</p>")

    assert index.character_offset("/body/DocFragment[1]/body/p/text().1") == 2


def test_an_inline_or_preformatted_elements_leading_whitespace_is_a_text_node() -> None:
    index = index_of("<p><span> <em>a</em>b</span></p><pre>  <em>c</em>d</pre>")

    assert index.character_offset("/body/DocFragment[1]/body/p/span/text()[2].0") == 1
    assert index.character_offset("/body/DocFragment[1]/body/pre/text()[2].0") == 3
