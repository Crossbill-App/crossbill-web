"""API router for chapter digests."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.reading.commands.chapter_digest.generate_chapter_digest_use_case import (
    GenerateChapterDigestUseCase,
)
from src.application.reading.commands.chapter_digest.update_digest_answers_use_case import (
    UpdateDigestAnswersUseCase,
)
from src.application.reading.queries.get_book_digests_use_case import (
    GetBookDigestsUseCase,
)
from src.application.reading.queries.get_chapter_digest_use_case import (
    GetChapterDigestUseCase,
)
from src.core import container
from src.domain.common.value_objects.ids import BookId, ChapterId, UserId
from src.domain.identity import User
from src.infrastructure.common.dependencies import require_ai_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.schemas.chapter_digest_schemas import (
    ChapterDigestResponse,
    DigestQuestionResponse,
    UpdateDigestAnswersRequest,
)

router = APIRouter(prefix="/chapters", tags=["digest"])


@router.get(
    "/{chapter_id}/digest",
    response_model=ChapterDigestResponse | None,
    status_code=status.HTTP_200_OK,
)
async def get_chapter_digest(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetChapterDigestUseCase = Depends(
        inject_use_case(container.reading.get_chapter_digest_use_case)
    ),
) -> ChapterDigestResponse | None:
    """Get a chapter's existing digest."""
    result = await use_case.get_digest(
        chapter_id=ChapterId(chapter_id),
        user_id=UserId(current_user.id.value),
    )

    if not result:
        return None

    return ChapterDigestResponse(
        id=result.id.value,
        chapter_id=result.chapter_id.value,
        summary=result.summary,
        keypoints=result.keypoints,
        questions=[
            DigestQuestionResponse(question=q.question, answer=q.answer, user_answer=q.user_answer)
            for q in result.questions
        ],
        generated_at=result.generated_at,
    )


@router.post(
    "/{chapter_id}/digest/generate",
    response_model=ChapterDigestResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_ai_enabled
async def generate_chapter_digest(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GenerateChapterDigestUseCase = Depends(
        inject_use_case(container.reading.generate_chapter_digest_use_case)
    ),
) -> ChapterDigestResponse:
    """Generate a chapter's digest."""
    result = await use_case.generate_digest(
        chapter_id=ChapterId(chapter_id),
        user_id=UserId(current_user.id.value),
    )

    return ChapterDigestResponse(
        id=result.id.value,
        chapter_id=result.chapter_id.value,
        summary=result.summary,
        keypoints=result.keypoints,
        questions=[
            DigestQuestionResponse(question=q.question, answer=q.answer, user_answer=q.user_answer)
            for q in result.questions
        ],
        generated_at=result.generated_at,
    )


@router.put(
    "/{chapter_id}/digest/answers",
    response_model=ChapterDigestResponse,
    status_code=status.HTTP_200_OK,
)
async def update_digest_answers(
    chapter_id: int,
    body: UpdateDigestAnswersRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: UpdateDigestAnswersUseCase = Depends(
        inject_use_case(container.reading.update_digest_answers_use_case)
    ),
) -> ChapterDigestResponse:
    """Update user answers for digest questions."""
    answers = {a.question_index: a.user_answer for a in body.answers}
    result = await use_case.update_answers(
        chapter_id=ChapterId(chapter_id),
        user_id=UserId(current_user.id.value),
        answers=answers,
    )

    return ChapterDigestResponse(
        id=result.id.value,
        chapter_id=result.chapter_id.value,
        summary=result.summary,
        keypoints=result.keypoints,
        questions=[
            DigestQuestionResponse(question=q.question, answer=q.answer, user_answer=q.user_answer)
            for q in result.questions
        ],
        generated_at=result.generated_at,
    )


book_digest_router = APIRouter(prefix="/books", tags=["digest"])


@book_digest_router.get(
    "/{book_id}/digest",
    response_model=CollectionResponse[ChapterDigestResponse],
    status_code=status.HTTP_200_OK,
)
async def get_book_digest(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetBookDigestsUseCase = Depends(
        inject_use_case(container.reading.get_book_digests_use_case)
    ),
) -> CollectionResponse[ChapterDigestResponse]:
    """Get the digest of every chapter in a book."""
    results = await use_case.get_all_digests_for_book(
        book_id=BookId(book_id),
        user_id=UserId(current_user.id.value),
    )

    return CollectionResponse[ChapterDigestResponse](
        items=[
            ChapterDigestResponse(
                id=r.id.value,
                chapter_id=r.chapter_id.value,
                summary=r.summary,
                keypoints=r.keypoints,
                questions=[
                    DigestQuestionResponse(
                        question=q.question, answer=q.answer, user_answer=q.user_answer
                    )
                    for q in r.questions
                ],
                generated_at=r.generated_at,
            )
            for r in results
        ]
    )
