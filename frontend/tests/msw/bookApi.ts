import type {
  BookDetails,
  BookReadingStageUpdateRequest,
  BookReadingStatistics,
  BookUpdateRequest,
  ChapterDigestResponse,
  Flashcard,
  FlashcardCreateRequest,
  FlashcardCreateResponse,
  FlashcardStatusRequest,
  FlashcardUpdateRequest,
  FlashcardUpdateResponse,
  Highlight,
  HighlightDeleteRequest,
  HighlightDeleteResponse,
  NoteCreateRequest,
  NoteFlashcardCreateRequest,
  NoteUpdateRequest,
  NoteWithLinks,
  ReadingSession,
  UpdateDigestAnswersRequest,
} from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aBookDetails, aFlashcard } from '../fixtures/book';
import { aNote } from '../fixtures/notes';
import { aBookActivity, aBookStatistics, noBookStatistics } from '../fixtures/sessions';

interface BookApiState {
  book: BookDetails;
  notes: NoteWithLinks[];
  digests: ChapterDigestResponse[];
  sessions: ReadingSession[];
  /** Defaults to the number of `sessions`; override to fake a paged total. */
  sessionTotal: number;
  statistics: BookReadingStatistics;
}

/**
 * Handlers backed by mutable state, so a mutation is visible to every request
 * that follows it. That is what makes "save, then the list refetches and shows
 * the new value" a real assertion instead of a coincidence.
 */
export function bookApi(initial: Partial<BookApiState> = {}) {
  const state: BookApiState = {
    book: initial.book ?? aBookDetails(),
    notes: initial.notes ?? [],
    digests: initial.digests ?? [],
    sessions: initial.sessions ?? [],
    sessionTotal: initial.sessionTotal ?? initial.sessions?.length ?? 0,
    // Counted off the sessions the handler was given, so a tab with no
    // sessions does not come with statistics summarising them anyway: an
    // unread book has nothing to average, to span, or to plot either.
    statistics:
      initial.statistics ??
      (initial.sessions?.length
        ? aBookStatistics({ session_count: initial.sessions.length, activity: aBookActivity() })
        : noBookStatistics()),
  };

  const findNote = (noteId: string | readonly string[] | undefined) =>
    state.notes.find((note) => note.id === Number(noteId));

  const allHighlights = () => state.book.chapters.flatMap((chapter) => chapter.highlights);

  const mapHighlights = (fn: (highlight: Highlight) => Highlight) => {
    state.book = {
      ...state.book,
      chapters: state.book.chapters.map((chapter) => ({
        ...chapter,
        highlights: chapter.highlights.map(fn),
      })),
    };
  };

  const allFlashcards = (): Flashcard[] => [
    ...allHighlights().flatMap((highlight) => highlight.flashcards),
    ...(state.book.book_flashcards ?? []),
    ...state.notes.flatMap((note) => note.flashcards ?? []),
  ];

  const newFlashcard = (body: FlashcardCreateRequest, overrides: Partial<Flashcard>) =>
    aFlashcard({
      id: Math.max(699, ...allFlashcards().map((card) => card.id)) + 1,
      book_id: state.book.id,
      question: body.question,
      answer: body.answer,
      ...overrides,
    });

  /**
   * Applies `change` to the card wherever the book and its notes embed it; null
   * removes it. Returns the changed card, if it is still there.
   */
  const changeFlashcard = (flashcardId: number, change: (card: Flashcard) => Flashcard | null) => {
    const changeAll = (cards: Flashcard[]) =>
      cards.flatMap((card) => {
        if (card.id !== flashcardId) return [card];
        const changed = change(card);
        return changed ? [changed] : [];
      });
    state.book = { ...state.book, book_flashcards: changeAll(state.book.book_flashcards ?? []) };
    mapHighlights((highlight) => ({ ...highlight, flashcards: changeAll(highlight.flashcards) }));
    state.notes = state.notes.map((note) => ({
      ...note,
      flashcards: changeAll(note.flashcards ?? []),
    }));
    return allFlashcards().find((candidate) => candidate.id === flashcardId);
  };

  const created = (flashcard: Flashcard) =>
    HttpResponse.json({
      success: true,
      message: 'Flashcard created',
      flashcard,
    } satisfies FlashcardCreateResponse);

  const handlers = [
    http.get('/api/v1/books/:bookId', () => HttpResponse.json(state.book)),
    http.get('/api/v1/flashcards/due', () =>
      HttpResponse.json({ items: [], total: 0, offset: 0, limit: 1 })
    ),
    http.get('/api/v1/books/:bookId/notes', () => HttpResponse.json({ items: state.notes })),
    http.get('/api/v1/books/:bookId/digest', () => HttpResponse.json({ items: state.digests })),

    http.put('/api/v1/chapters/:chapterId/digest/answers', async ({ params, request }) => {
      const digest = state.digests.find(
        (candidate) => candidate.chapter_id === Number(params.chapterId)
      );
      if (!digest) {
        return new HttpResponse(null, { status: 404 });
      }

      const body = (await request.json()) as UpdateDigestAnswersRequest;
      const updated: ChapterDigestResponse = {
        ...digest,
        questions: digest.questions.map((question, index) => ({
          ...question,
          user_answer:
            body.answers.find((answer) => answer.question_index === index)?.user_answer ??
            question.user_answer,
        })),
      };
      state.digests = state.digests.map((candidate) =>
        candidate.chapter_id === updated.chapter_id ? updated : candidate
      );

      return HttpResponse.json(updated);
    }),
    // Paging is the page's own arithmetic over `total`; the handler serves
    // whatever `sessions` holds and only echoes back the window it was asked for.
    http.get('/api/v1/books/:bookId/reading_sessions', ({ request }) => {
      const params = new URL(request.url).searchParams;
      return HttpResponse.json({
        items: state.sessions,
        total: state.sessionTotal,
        offset: Number(params.get('offset') ?? 0),
        limit: Number(params.get('limit') ?? state.sessions.length),
      });
    }),
    http.get('/api/v1/books/:bookId/statistics', () => HttpResponse.json(state.statistics)),
    http.get('/api/v1/jobs/books/:bookId/digest', () => HttpResponse.json(null)),
    http.get('/api/v1/books/:bookId/tags', () => HttpResponse.json({ items: [] })),
    http.get('/api/v1/books/:bookId/highlight-labels', () => HttpResponse.json({ items: [] })),

    http.put('/api/v1/books/:bookId/reading-stage', async ({ request }) => {
      const body = (await request.json()) as BookReadingStageUpdateRequest;
      state.book = { ...state.book, reading_stage: body.reading_stage ?? null };
      return new HttpResponse(null, { status: 204 });
    }),

    http.patch('/api/v1/books/:bookId', async ({ request }) => {
      const body = (await request.json()) as BookUpdateRequest;
      if ('description' in body) {
        // Mirrors the server, which normalises blank/whitespace-only text to null.
        const next = body.description?.trim();
        state.book = { ...state.book, description: next || null };
      }
      return new HttpResponse(null, { status: 204 });
    }),

    http.delete('/api/v1/books/:bookId', () => new HttpResponse(null, { status: 204 })),

    http.delete('/api/v1/books/:bookId/highlight', async ({ request }) => {
      const { highlight_ids } = (await request.json()) as HighlightDeleteRequest;
      const isDeleted = (highlight: Highlight) => highlight_ids.includes(highlight.id);
      const deleted_count = allHighlights().filter(isDeleted).length;
      state.book = {
        ...state.book,
        chapters: state.book.chapters.map((chapter) => ({
          ...chapter,
          highlights: chapter.highlights.filter((highlight) => !isDeleted(highlight)),
        })),
      };

      return HttpResponse.json({
        success: true,
        message: 'Highlights deleted',
        deleted_count,
      } satisfies HighlightDeleteResponse);
    }),

    http.post('/api/v1/books/:bookId/flashcards', async ({ request }) => {
      const body = (await request.json()) as FlashcardCreateRequest;
      const flashcard = newFlashcard(body, { chapter_id: body.chapter_id ?? null });
      state.book = {
        ...state.book,
        book_flashcards: [...(state.book.book_flashcards ?? []), flashcard],
      };
      return created(flashcard);
    }),

    http.post('/api/v1/highlights/:highlightId/flashcards', async ({ params, request }) => {
      const body = (await request.json()) as FlashcardCreateRequest;
      const highlightId = Number(params.highlightId);
      const highlight = allHighlights().find((candidate) => candidate.id === highlightId);
      if (!highlight) {
        return new HttpResponse(null, { status: 404 });
      }

      const flashcard = newFlashcard(body, {
        highlight_id: highlightId,
        chapter_id: highlight.chapter_id ?? null,
      });
      mapHighlights((candidate) =>
        candidate.id === highlightId
          ? { ...candidate, flashcards: [...candidate.flashcards, flashcard] }
          : candidate
      );
      return created(flashcard);
    }),

    http.post('/api/v1/notes/:noteId/flashcards', async ({ params, request }) => {
      const body = (await request.json()) as NoteFlashcardCreateRequest;
      const note = findNote(params.noteId);
      if (!note) {
        return new HttpResponse(null, { status: 404 });
      }

      const flashcard = newFlashcard(body, {
        book_id: body.book_id ?? note.book_ids[0],
        note_id: note.id,
      });
      state.notes = state.notes.map((candidate) =>
        candidate.id === note.id
          ? { ...candidate, flashcards: [...(candidate.flashcards ?? []), flashcard] }
          : candidate
      );
      state.book = {
        ...state.book,
        book_flashcards: [...(state.book.book_flashcards ?? []), flashcard],
      };
      return created(flashcard);
    }),

    http.put('/api/v1/flashcards/:flashcardId', async ({ params, request }) => {
      const body = (await request.json()) as FlashcardUpdateRequest;
      const updated = changeFlashcard(Number(params.flashcardId), (card) => ({
        ...card,
        question: body.question ?? card.question,
        answer: body.answer ?? card.answer,
      }));
      if (!updated) {
        return new HttpResponse(null, { status: 404 });
      }

      return HttpResponse.json({
        success: true,
        message: 'Flashcard updated',
        flashcard: updated,
      } satisfies FlashcardUpdateResponse);
    }),

    http.put('/api/v1/flashcards/:flashcardId/status', async ({ params, request }) => {
      const body = (await request.json()) as FlashcardStatusRequest;
      const updated = changeFlashcard(Number(params.flashcardId), (card) => ({
        ...card,
        status: body.status,
      }));
      return updated ? HttpResponse.json(updated) : new HttpResponse(null, { status: 404 });
    }),

    http.delete('/api/v1/flashcards/:flashcardId', ({ params }) => {
      changeFlashcard(Number(params.flashcardId), () => null);
      return HttpResponse.json({ success: true, message: 'Flashcard deleted' });
    }),

    http.post('/api/v1/notes', async ({ request }) => {
      const body = (await request.json()) as NoteCreateRequest;
      const note = aNote({
        id: Math.max(0, ...state.notes.map((candidate) => candidate.id)) + 1,
        title: body.title,
        body: body.body ?? '',
        kind: body.kind ?? null,
        book_ids: [body.book_id],
        chapter_ids: body.chapter_ids ?? [],
        highlight_ids: body.highlight_ids ?? [],
        tag_ids: body.tag_ids ?? [],
      });
      state.notes = [...state.notes, note];

      return HttpResponse.json({ success: true, message: 'Note created', note });
    }),

    http.delete('/api/v1/notes/:noteId', ({ params }) => {
      state.notes = state.notes.filter((candidate) => candidate.id !== Number(params.noteId));
      return HttpResponse.json({ success: true, message: 'Note deleted' });
    }),

    http.get('/api/v1/notes/:noteId', ({ params }) => {
      const note = findNote(params.noteId);
      return note ? HttpResponse.json(note) : new HttpResponse(null, { status: 404 });
    }),

    http.put('/api/v1/notes/:noteId', async ({ params, request }) => {
      const note = findNote(params.noteId);
      if (!note) {
        return new HttpResponse(null, { status: 404 });
      }

      const body = (await request.json()) as NoteUpdateRequest;
      const updated: NoteWithLinks = {
        ...note,
        title: body.title,
        body: body.body ?? '',
        kind: body.kind ?? null,
        chapter_ids: body.chapter_ids ?? [],
        highlight_ids: body.highlight_ids ?? [],
        tag_ids: body.tag_ids ?? [],
      };
      state.notes = state.notes.map((candidate) =>
        candidate.id === updated.id ? updated : candidate
      );

      return HttpResponse.json({ success: true, message: 'Note updated', note: updated });
    }),
  ];

  return { handlers, state };
}
