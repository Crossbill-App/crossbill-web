import type { BookDetails, NoteUpdateRequest, NoteWithLinks } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';
import { aBookDetails } from '../fixtures/book';

interface BookApiState {
  book: BookDetails;
  notes: NoteWithLinks[];
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
  };

  const findNote = (noteId: string | readonly string[] | undefined) =>
    state.notes.find((note) => note.id === Number(noteId));

  const handlers = [
    http.get('/api/v1/books/:bookId', () => HttpResponse.json(state.book)),
    http.get('/api/v1/books/:bookId/notes', () => HttpResponse.json({ items: state.notes })),
    http.get('/api/v1/books/:bookId/digest', () => HttpResponse.json({ items: [] })),
    http.get('/api/v1/books/:bookId/reading_sessions', () =>
      HttpResponse.json({ items: [], total: 0, offset: 0, limit: 1 })
    ),
    http.get('/api/v1/jobs/books/:bookId/digest', () => HttpResponse.json(null)),

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
