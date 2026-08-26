from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.book import Book, ReadingStage
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.library.orm.book_model import Book as BookORM


class BookMapper:
    """Mapper for Book ORM ↔ Domain conversion."""

    def to_domain(self, orm_model: BookORM) -> Book:
        """Convert ORM model to domain entity."""
        return Book.create_with_id(
            id=BookId(orm_model.id),
            user_id=UserId(orm_model.user_id),
            title=orm_model.title,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
            client_book_id=orm_model.client_book_id,
            author=orm_model.author,
            isbn=orm_model.isbn,
            description=orm_model.description,
            language=orm_model.language,
            page_count=orm_model.page_count,
            ebook_file=orm_model.ebook_file,
            file_type=orm_model.file_type,
            cover_file=orm_model.cover_file,
            cover_blurhash=orm_model.cover_blurhash,
            last_viewed=orm_model.last_viewed,
            last_synced=orm_model.last_synced,
            end_position=Position.from_json(orm_model.end_position)
            if orm_model.end_position
            else None,
            reading_stage=ReadingStage(orm_model.reading_stage)
            if orm_model.reading_stage
            else None,
        )

    def to_orm(self, domain_entity: Book, orm_model: BookORM | None = None) -> BookORM:
        """Convert domain entity to ORM model."""
        if orm_model is None:
            orm_model = BookORM(
                id=orm_id(domain_entity.id),
                created_at=domain_entity.created_at,
            )
        orm_model.user_id = domain_entity.user_id.value
        orm_model.title = domain_entity.title
        orm_model.client_book_id = domain_entity.client_book_id
        orm_model.author = domain_entity.author
        orm_model.isbn = domain_entity.isbn
        orm_model.description = domain_entity.description
        orm_model.language = domain_entity.language
        orm_model.page_count = domain_entity.page_count
        orm_model.ebook_file = domain_entity.ebook_file
        orm_model.file_type = domain_entity.file_type
        orm_model.cover_file = domain_entity.cover_file
        orm_model.cover_blurhash = domain_entity.cover_blurhash
        orm_model.last_viewed = domain_entity.last_viewed
        orm_model.last_synced = domain_entity.last_synced
        orm_model.end_position = (
            domain_entity.end_position.to_json() if domain_entity.end_position else None
        )
        orm_model.reading_stage = (
            domain_entity.reading_stage.value if domain_entity.reading_stage else None
        )
        return orm_model
