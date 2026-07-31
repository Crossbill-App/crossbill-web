import type { NoteWithLinks } from '@/api/generated/model';

export const aNote = (overrides: Partial<NoteWithLinks> = {}): NoteWithLinks => ({
  id: 100,
  user_id: 1,
  title: 'Ada Lovelace',
  body: 'The first programmer.',
  kind: 'character',
  book_ids: [1],
  chapter_ids: [],
  highlight_ids: [],
  tag_ids: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  chapters: [],
  highlights: [],
  tags: [],
  flashcards: [],
  ...overrides,
});
