import type {
  BookDetails,
  BookReadingStageUpdateRequest,
  BookReadingStatistics,
  BookUpdateRequest,
  ChapterDigestResponse,
  NoteCreateRequest,
  NoteUpdateRequest,
  NoteWithLinks,
  ReadingSession,
  UpdateDigestAnswersRequest,
} from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aBookDetails } from '../fixtures/book';
import { aNote } from '../fixtures/notes';
import { aBookActivity, aBookStatistics } from '../fixtures/sessions';

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
    // sessions does not come with statistics summarising them anyway.
    statistics:
      initial.statistics ??
      aBookStatistics({
        session_count: initial.sessions?.length ?? 0,
        // A tab with no sessions gets no grid, for the same reason it gets no
        // summary: there is nothing for either to be about.
        activity: initial.sessions?.length ? aBookActivity() : null,
      }),
  };

  const findNote = (noteId: string | readonly string[] | undefined) =>
    state.notes.find((note) => note.id === Number(noteId));

  const handlers = [
    http.get('/api/v1/books/:bookId', () => HttpResponse.json(state.book)),
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
