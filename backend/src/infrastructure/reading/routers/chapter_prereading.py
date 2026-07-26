"""API router for chapter prereading content."""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.reading.commands.chapter_prereading.generate_chapter_prereading_use_case import (
    GenerateChapterPrereadingUseCase,
)
from src.application.reading.commands.chapter_prereading.update_prereading_answers_use_case import (
    UpdatePrereadingAnswersUseCase,
)
from src.application.reading.queries.get_book_prereading_use_case import (
    GetBookPrereadingUseCase,
)
from src.application.reading.queries.get_chapter_prereading_use_case import (
    GetChapterPrereadingUseCase,
)
from src.core import container
from src.domain.common.value_objects.ids import BookId, ChapterId, UserId
from src.domain.identity import User
from src.infrastructure.common.dependencies import require_ai_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.reading.schemas.chapter_prereading_schemas import (
    ChapterPrereadingResponse,
    PrereadingQuestionResponse,
    UpdatePrereadingAnswersRequest,
)

router = APIRouter(prefix="/chapters", tags=["prereading"])


@router.get(
    "/{chapter_id}/prereading",
    response_model=ChapterPrereadingResponse | None,
    status_code=status.HTTP_200_OK,
)
async def get_chapter_prereading(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetChapterPrereadingUseCase = Depends(
        inject_use_case(container.reading.get_chapter_prereading_use_case)
    ),
) -> ChapterPrereadingResponse | None:
    """Get existing prereading content for a chapter."""
    result = await use_case.get_prereading_content(
        chapter_id=ChapterId(chapter_id),
        user_id=UserId(current_user.id.value),
    )

    if not result:
        return None

    return ChapterPrereadingResponse(
        id=result.id.value,
        chapter_id=result.chapter_id.value,
        summary=result.summary,
        keypoints=result.keypoints,
        questions=[
            PrereadingQuestionResponse(
                question=q.question, answer=q.answer, user_answer=q.user_answer
            )
            for q in result.questions
        ],
        generated_at=result.generated_at,
    )


@router.post(
    "/{chapter_id}/prereading/generate",
    response_model=ChapterPrereadingResponse,
    status_code=status.HTTP_201_CREATED,
)
@require_ai_enabled
async def generate_chapter_prereading(
    chapter_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GenerateChapterPrereadingUseCase = Depends(
        inject_use_case(container.reading.generate_chapter_prereading_use_case)
    ),
) -> ChapterPrereadingResponse:
    """Generate prereading content for a chapter."""
    result = await use_case.generate_prereading_content(
        chapter_id=ChapterId(chapter_id),
        user_id=UserId(current_user.id.value),
    )

    return ChapterPrereadingResponse(
        id=result.id.value,
        chapter_id=result.chapter_id.value,
        summary=result.summary,
        keypoints=result.keypoints,
        questions=[
            PrereadingQuestionResponse(
                question=q.question, answer=q.answer, user_answer=q.user_answer
            )
            for q in result.questions
        ],
        generated_at=result.generated_at,
    )


@router.put(
    "/{chapter_id}/prereading/answers",
    response_model=ChapterPrereadingResponse,
    status_code=status.HTTP_200_OK,
)
async def update_prereading_answers(
    chapter_id: int,
    body: UpdatePrereadingAnswersRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: UpdatePrereadingAnswersUseCase = Depends(
        inject_use_case(container.reading.update_prereading_answers_use_case)
    ),
) -> ChapterPrereadingResponse:
    """Update user answers for prereading questions."""
    answers = {a.question_index: a.user_answer for a in body.answers}
    result = await use_case.update_answers(
        chapter_id=ChapterId(chapter_id),
        user_id=UserId(current_user.id.value),
        answers=answers,
    )

    return ChapterPrereadingResponse(
        id=result.id.value,
        chapter_id=result.chapter_id.value,
        summary=result.summary,
        keypoints=result.keypoints,
        questions=[
            PrereadingQuestionResponse(
                question=q.question, answer=q.answer, user_answer=q.user_answer
            )
            for q in result.questions
        ],
        generated_at=result.generated_at,
    )


book_prereading_router = APIRouter(prefix="/books", tags=["prereading"])


@book_prereading_router.get(
    "/{book_id}/prereading",
    response_model=CollectionResponse[ChapterPrereadingResponse],
    status_code=status.HTTP_200_OK,
)
async def get_book_prereading(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetBookPrereadingUseCase = Depends(
        inject_use_case(container.reading.get_book_prereading_use_case)
    ),
) -> CollectionResponse[ChapterPrereadingResponse]:
    """Get all prereading content for chapters in a book."""
    results = await use_case.get_all_prereading_for_book(
        book_id=BookId(book_id),
        user_id=UserId(current_user.id.value),
    )

    return CollectionResponse[ChapterPrereadingResponse](
        items=[
            ChapterPrereadingResponse(
                id=r.id.value,
                chapter_id=r.chapter_id.value,
                summary=r.summary,
                keypoints=r.keypoints,
                questions=[
                    PrereadingQuestionResponse(
                        question=q.question, answer=q.answer, user_answer=q.user_answer
                    )
                    for q in r.questions
                ],
                generated_at=r.generated_at,
            )
            for r in results
        ]
    )
