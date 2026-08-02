"""Mapper for ChapterDigest ORM ↔ Domain conversion."""

from src.domain.common.value_objects.ids import ChapterDigestId, ChapterId
from src.domain.reading.entities.chapter_digest import (
    ChapterDigest,
    DigestQuestion,
)
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.reading.orm.chapter_digest_model import (
    ChapterDigest as ChapterDigestORM,
)


class ChapterDigestMapper:
    """Mapper between ChapterDigest domain entity and ORM model."""

    def to_domain(self, orm: ChapterDigestORM) -> ChapterDigest:
        """Convert ORM model to domain entity."""
        return ChapterDigest.create_with_id(
            id=ChapterDigestId(orm.id),
            chapter_id=ChapterId(orm.chapter_id),
            questions=[
                DigestQuestion(
                    question=q["question"],
                    answer=q["answer"],
                    user_answer=q.get("user_answer", ""),
                )
                for q in orm.questions
            ],
            summary=orm.summary,
            keypoints=orm.keypoints,
            generated_at=orm.generated_at,
            ai_model=orm.ai_model,
        )

    def to_orm(
        self, entity: ChapterDigest, orm: ChapterDigestORM | None = None
    ) -> ChapterDigestORM:
        """Convert domain entity to ORM model."""
        questions = [
            {"question": q.question, "answer": q.answer, "user_answer": q.user_answer}
            for q in entity.questions
        ]

        if orm is None:
            orm = ChapterDigestORM(
                id=orm_id(entity.id),
            )
        orm.chapter_id = entity.chapter_id.value
        orm.summary = entity.summary
        orm.keypoints = entity.keypoints
        orm.questions = questions
        orm.generated_at = entity.generated_at
        orm.ai_model = entity.ai_model
        return orm
