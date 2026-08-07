import type { DigestSearchItem, NoteSearchItem } from '@/api/generated/model';

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
  ...overrides,
});

/**
 * @public Unused within this task — the Notes tab's search tests are the next
 * consumer.
 */
export const aNoteHit = (overrides: Partial<NoteSearchItem> = {}): NoteSearchItem => ({
  score: 0.7,
  id: 100,
  books: [{ id: 1, title: 'The Pragmatic Reader' }],
  title: 'Ada Lovelace',
  body: 'The first programmer.',
  kind: 'character',
  ...overrides,
});
