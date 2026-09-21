"""Recolouring one highlight without repainting its neighbours.

The colour a passage is drawn in belongs to the highlight; the label naming that
colour belongs to the style every highlight of that colour in the book shares. So
``PATCH .../highlights/{id}/color`` moves one highlight to another style, where
``PATCH /highlight-labels/{id}`` renames or recolours the style itself -- which is
what made a reader's other yellow highlights turn red with the one they meant.
"""

from typing import Any, TypedDict, Unpack

from fastapi import status
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import (
    create_test_book,
    create_test_chapter,
    create_test_highlight,
    create_test_highlight_style,
)
from tests.readium_helpers import another_users_book

DEFAULT_USER_ID = 1

# KOReader's own hues for two of its nine colours, as the resolver fills them in
# for a style whose label names no colour of its own.
YELLOW = "#F59E0B"
RED = "#EF4444"


def url(book_id: int, highlight_id: int) -> str:
    return f"/api/v1/books/{book_id}/highlights/{highlight_id}/color"


class Colour(TypedDict, total=False):
    device_color: str
    device_style: str


async def recolour(
    client: AsyncClient,
    book: models.Book,
    highlight: models.Highlight,
    **body: Unpack[Colour],
) -> Response:
    return await client.patch(url(book.id, highlight.id), json=body)


async def a_book_of_two_yellow_highlights(
    db_session: AsyncSession,
) -> tuple[models.Book, models.Highlight, models.Highlight, models.HighlightStyle]:
    """Two passages marked with the same highlighter, as the reader's default makes them."""
    book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Two Yellows", author="A"
    )
    chapter = await create_test_chapter(db_session, book, name="One", chapter_number=1)
    style = await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=book.id,
        device_color="yellow",
        device_style="lighten",
    )
    first = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="The lantern went out",
        datetime_str="2024-01-15 14:00:00",
        chapter_id=chapter.id,
        highlight_style_id=style.id,
    )
    second = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="Morning arrived without ceremony",
        datetime_str="2024-01-15 15:00:00",
        chapter_id=chapter.id,
        highlight_style_id=style.id,
    )
    return book, first, second, style


async def stored_labels(client: AsyncClient, book: models.Book) -> list[dict[str, Any]]:
    response = await client.get(f"/api/v1/books/{book.id}/highlight-labels")
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["items"]


async def drawn_highlights(client: AsyncClient, book: models.Book) -> dict[int, dict[str, Any]]:
    """Every highlight of the book as the reader draws it, by id."""
    response = await client.get(f"/api/v1/books/{book.id}")
    assert response.status_code == status.HTTP_200_OK, response.text
    return {
        highlight["id"]: highlight
        for chapter in response.json()["chapters"]
        for highlight in chapter["highlights"]
    }


async def test_recolouring_one_highlight_leaves_its_neighbour_in_its_own_colour(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, first, second, yellow = await a_book_of_two_yellow_highlights(db_session)

    response = await recolour(client, book, second, device_color="red")

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["ui_color"] == RED
    assert response.json()["highlight_style_id"] != yellow.id

    drawn = await drawn_highlights(client, book)
    assert drawn[second.id]["label"]["ui_color"] == RED
    assert drawn[first.id]["label"]["ui_color"] == YELLOW
    assert drawn[first.id]["label"]["highlight_style_id"] == yellow.id


async def test_the_colour_a_highlight_moves_to_gets_the_books_style_created_for_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, _, second, yellow = await a_book_of_two_yellow_highlights(db_session)

    body = (await recolour(client, book, second, device_color="red")).json()

    styles = (
        (
            await db_session.execute(
                select(models.HighlightStyle)
                .filter_by(book_id=book.id)
                .order_by(models.HighlightStyle.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    assert [(style.device_color, style.device_style) for style in styles] == [
        ("yellow", "lighten"),
        ("red", "lighten"),
    ]
    assert styles[1].id == body["highlight_style_id"]
    assert styles[0].id == yellow.id


async def test_the_book_keeps_a_colour_the_last_highlight_in_it_left_behind(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Yellow stays offerable: the style is the book's, not the highlight's."""
    book, first, second, yellow = await a_book_of_two_yellow_highlights(db_session)

    await recolour(client, book, first, device_color="red")
    await recolour(client, book, second, device_color="red")

    labels = await stored_labels(client, book)
    by_colour = {label["device_color"]: label for label in labels}
    assert by_colour["yellow"]["highlight_count"] == 0
    assert by_colour["yellow"]["id"] == yellow.id
    assert by_colour["red"]["highlight_count"] == 2


async def test_a_highlight_moved_to_a_labelled_colour_wears_that_label(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, _, second, _ = await a_book_of_two_yellow_highlights(db_session)
    await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=book.id,
        device_color="red",
        device_style="lighten",
        label="Disagree",
        ui_color="#111111",
    )

    body = (await recolour(client, book, second, device_color="red")).json()

    assert body["text"] == "Disagree"
    assert body["ui_color"] == "#111111"
    assert (await drawn_highlights(client, book))[second.id]["label"]["text"] == "Disagree"


async def test_a_drawer_sent_with_the_colour_is_what_it_is_filed_under(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, _, second, _ = await a_book_of_two_yellow_highlights(db_session)

    body = (
        await recolour(client, book, second, device_color="red", device_style="underscore")
    ).json()

    labels = {label["id"]: label for label in await stored_labels(client, book)}
    assert labels[body["highlight_style_id"]]["device_style"] == "underscore"


async def test_the_colour_a_highlight_already_wears_is_no_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, _, second, yellow = await a_book_of_two_yellow_highlights(db_session)

    response = await recolour(client, book, second, device_color="yellow")

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["highlight_style_id"] == yellow.id


async def test_a_colour_that_names_nothing_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, _, second, yellow = await a_book_of_two_yellow_highlights(db_session)

    response = await recolour(client, book, second, device_color="  ")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert (await drawn_highlights(client, book))[second.id]["label"][
        "highlight_style_id"
    ] == yellow.id


async def test_a_highlight_of_another_book_is_not_this_books_to_recolour(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    book, _, second, yellow = await a_book_of_two_yellow_highlights(db_session)
    elsewhere = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Elsewhere", author="A"
    )

    response = await recolour(client, elsewhere, second, device_color="red")

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert (await drawn_highlights(client, book))[second.id]["label"][
        "highlight_style_id"
    ] == yellow.id


async def test_another_readers_highlight_is_not_ours_to_recolour(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    theirs = await another_users_book(db_session)
    their_style = await create_test_highlight_style(
        db_session=db_session,
        user_id=theirs.user_id,
        book_id=theirs.id,
        device_color="yellow",
        device_style="lighten",
    )
    their_highlight = await create_test_highlight(
        db_session=db_session,
        book=theirs,
        user_id=theirs.user_id,
        text="Not yours to recolour",
        datetime_str="2024-01-15 14:00:00",
        highlight_style_id=their_style.id,
    )

    response = await recolour(client, theirs, their_highlight, device_color="red")

    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    await db_session.refresh(their_highlight)
    assert their_highlight.highlight_style_id == their_style.id
