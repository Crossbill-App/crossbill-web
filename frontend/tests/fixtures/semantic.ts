import type { DigestSearchItem, HighlightSearchItem, NoteSearchItem } from '@/api/generated/model';

export const aDigestHit = (overrides: Partial<DigestSearchItem> = {}): DigestSearchItem => ({
  score: 0.7,
  id: 500,
  book_id: 1,
  book_title: 'The Pragmatic Reader',
  chapter_id: 10,
  chapter_name: 'Chapter One',
  chapter_number: 1,
  summary: 'A summary of the chapter.',
  keypoints: [],
  cover_file: null,
  cover_blurhash: null,
  ...overrides,
});

export const aNoteHit = (overrides: Partial<NoteSearchItem> = {}): NoteSearchItem => ({
  score: 0.7,
  id: 100,
  books: [{ id: 1, title: 'The Pragmatic Reader', cover_file: null, cover_blurhash: null }],
  title: 'Ada Lovelace',
  body: 'The first programmer.',
  kind: 'character',
  ...overrides,
});

export const aHighlightHit = (
  overrides: Partial<HighlightSearchItem> = {}
): HighlightSearchItem => ({
  score: 0.7,
  id: 300,
  book_id: 1,
  book_title: 'The Pragmatic Reader',
  chapter_id: 10,
  chapter_name: 'Chapter One',
  chapter_number: 1,
  text: 'The map is not the territory.',
  page: 42,
  datetime: '2026-01-01T00:00:00',
  cover_file: null,
  cover_blurhash: null,
  ...overrides,
});
