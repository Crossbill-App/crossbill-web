"""Tests for PublicationRepository.

No endpoint reads a stored publication yet, so this is the only tier where the
ownership check on ``get`` can be exercised at all.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects import BookId, UserId
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository

FIXTURES = Path(__file__).parent / "fixtures"


def parse_fixture(name: str) -> ParsedPublication:
    return read_publication((FIXTURES / f"{name}.epub").read_bytes())


@pytest.fixture
def publication_repository(db_session: AsyncSession) -> PublicationRepository:
    return PublicationRepository(db_session)


@pytest.fixture
def minimal_publication() -> ParsedPublication:
    return parse_fixture("minimal")


@pytest.fixture
async def other_user(db_session: AsyncSession) -> models.User:
    user = models.User(email="intruder@test.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestPublicationRepositorySave:
    async def test_save_then_get_returns_an_equal_publication(
        self,
        publication_repository: PublicationRepository,
        test_book: models.Book,
        test_user: models.User,
        minimal_publication: ParsedPublication,
    ) -> None:
        await publication_repository.save(BookId(test_book.id), "minimal.epub", minimal_publication)

        stored = await publication_repository.get(BookId(test_book.id), UserId(test_user.id))

        assert stored == minimal_publication

    async def test_save_records_the_file_name_and_content_hash(
        self,
        publication_repository: PublicationRepository,
        db_session: AsyncSession,
        test_book: models.Book,
        minimal_publication: ParsedPublication,
    ) -> None:
        await publication_repository.save(BookId(test_book.id), "minimal.epub", minimal_publication)

        result = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=test_book.id)
        )
        row = result.scalar_one()
        assert row.file_name == "minimal.epub"
        assert row.content_hash == minimal_publication.content_hash
        assert row.derived_at is not None

    async def test_saving_again_replaces_the_row(
        self,
        publication_repository: PublicationRepository,
        db_session: AsyncSession,
        test_book: models.Book,
        test_user: models.User,
        minimal_publication: ParsedPublication,
    ) -> None:
        replacement = parse_fixture("nested_toc")
        assert replacement.content_hash != minimal_publication.content_hash

        await publication_repository.save(BookId(test_book.id), "minimal.epub", minimal_publication)
        await publication_repository.save(BookId(test_book.id), "nested_toc.epub", replacement)

        count = await db_session.scalar(select(func.count()).select_from(models.BookPublication))
        stored = await publication_repository.get(BookId(test_book.id), UserId(test_user.id))
        assert count == 1
        assert stored == replacement


class TestPublicationRepositoryGet:
    async def test_get_without_a_stored_publication_returns_none(
        self,
        publication_repository: PublicationRepository,
        test_book: models.Book,
        test_user: models.User,
    ) -> None:
        assert await publication_repository.get(BookId(test_book.id), UserId(test_user.id)) is None

    async def test_another_users_book_returns_none(
        self,
        publication_repository: PublicationRepository,
        test_book: models.Book,
        other_user: models.User,
        minimal_publication: ParsedPublication,
    ) -> None:
        await publication_repository.save(BookId(test_book.id), "minimal.epub", minimal_publication)

        intruder = UserId(other_user.id)

        assert await publication_repository.get(BookId(test_book.id), intruder) is None


class TestPublicationRepositoryDelete:
    async def test_delete_removes_the_row(
        self,
        publication_repository: PublicationRepository,
        db_session: AsyncSession,
        test_book: models.Book,
        minimal_publication: ParsedPublication,
    ) -> None:
        await publication_repository.save(BookId(test_book.id), "minimal.epub", minimal_publication)

        await publication_repository.delete(BookId(test_book.id))

        result = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=test_book.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_without_a_stored_publication_does_not_raise(
        self, publication_repository: PublicationRepository, test_book: models.Book
    ) -> None:
        await publication_repository.delete(BookId(test_book.id))
