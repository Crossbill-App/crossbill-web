import type { BookDetails, ChapterWithHighlights } from '@/api/generated/model';

export const aChapter = (
  overrides: Partial<ChapterWithHighlights> = {}
): ChapterWithHighlights => ({
  id: 10,
  name: 'Chapter One',
  chapter_number: 1,
  parent_id: null,
  start_position: null,
  highlights: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

export const aBookDetails = (overrides: Partial<BookDetails> = {}): BookDetails => ({
  id: 1,
  title: 'The Pragmatic Reader',
  author: 'Ada Lovelace',
  isbn: null,
  cover_file: null,
  cover_blurhash: null,
  description: null,
  language: 'en',
  page_count: 320,
  tags: [],
  tag_groups: [],
  bookmarks: [],
  book_flashcards: [],
  chapters: [aChapter()],
  reading_position: null,
  end_position: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  last_viewed: null,
  ...overrides,
});
