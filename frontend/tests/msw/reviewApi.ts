import type {
  DueFlashcard,
  Flashcard,
  FlashcardReviewRequest,
  FlashcardReviewRequestRating,
  FlashcardStatusRequest,
  FlashcardUpdateRequest,
  FlashcardUpdateResponse,
  PaginatedResponseDueFlashcard,
} from '@/api/generated/model';
import { omit } from 'lodash';
import { http, HttpResponse } from 'msw';

interface RecordedReview {
  flashcardId: number;
  rating: FlashcardReviewRequestRating;
}

interface DueListRequest {
  bookId: number | null;
  limit: number;
  offset: number;
}

const asFlashcard = (card: DueFlashcard): Flashcard =>
  omit(card, ['book_title', 'chapter_name', 'highlight_text', 'note_title', 'previews']);

/**
 * The due list and the calls a review makes on it. A reviewed, suspended or
 * deleted card leaves the list the next GET serves, as on the server.
 */
export const reviewApi = ({ cards }: { cards: DueFlashcard[] }) => {
  const state = {
    cards: [...cards],
    reviews: [] as RecordedReview[],
    dueListRequests: [] as DueListRequest[],
  };

  const isDue = (card: DueFlashcard) =>
    card.status === 'active' && !state.reviews.some((review) => review.flashcardId === card.id);

  const findCard = (flashcardId: string | readonly string[] | undefined) =>
    state.cards.find((card) => card.id === Number(flashcardId));

  const changeCard = (flashcardId: number, change: (card: DueFlashcard) => DueFlashcard) => {
    state.cards = state.cards.map((card) => (card.id === flashcardId ? change(card) : card));
  };

  const handlers = [
    http.get('/api/v1/flashcards/due', ({ request }) => {
      const params = new URL(request.url).searchParams;
      const bookId = params.has('book_id') ? Number(params.get('book_id')) : null;
      const limit = Number(params.get('limit') ?? 50);
      const offset = Number(params.get('offset') ?? 0);
      state.dueListRequests.push({ bookId, limit, offset });

      const due = state.cards.filter(
        (card) => isDue(card) && (bookId === null || card.book_id === bookId)
      );
      return HttpResponse.json({
        items: due.slice(offset, offset + limit),
        total: due.length,
        offset,
        limit,
      } satisfies PaginatedResponseDueFlashcard);
    }),

    http.post('/api/v1/flashcards/:flashcardId/reviews', async ({ params, request }) => {
      const card = findCard(params.flashcardId);
      if (!card) return new HttpResponse(null, { status: 404 });

      const body = (await request.json()) as FlashcardReviewRequest;
      state.reviews.push({ flashcardId: card.id, rating: body.rating });
      return HttpResponse.json(asFlashcard(card));
    }),

    http.put('/api/v1/flashcards/:flashcardId/status', async ({ params, request }) => {
      const card = findCard(params.flashcardId);
      if (!card) return new HttpResponse(null, { status: 404 });

      const body = (await request.json()) as FlashcardStatusRequest;
      changeCard(card.id, (candidate) => ({ ...candidate, status: body.status }));
      return HttpResponse.json(asFlashcard({ ...card, status: body.status }));
    }),

    http.put('/api/v1/flashcards/:flashcardId', async ({ params, request }) => {
      const card = findCard(params.flashcardId);
      if (!card) return new HttpResponse(null, { status: 404 });

      const body = (await request.json()) as FlashcardUpdateRequest;
      const updated = {
        ...card,
        question: body.question ?? card.question,
        answer: body.answer ?? card.answer,
      };
      changeCard(card.id, () => updated);
      return HttpResponse.json({
        success: true,
        message: 'Flashcard updated',
        flashcard: asFlashcard(updated),
      } satisfies FlashcardUpdateResponse);
    }),

    http.delete('/api/v1/flashcards/:flashcardId', ({ params }) => {
      state.cards = state.cards.filter((card) => card.id !== Number(params.flashcardId));
      return HttpResponse.json({ success: true, message: 'Flashcard deleted' });
    }),
  ];

  return { handlers, state };
};
