import type {
  BookDetails,
  BookWithHighlightCount,
  ChapterWithHighlights,
  Highlight,
} from '@/api/generated/model';

export const aHighlight = (overrides: Partial<Highlight> = {}): Highlight => ({
  id: 300,
  book_id: 1,
  chapter_id: 10,
  chapter: 'Chapter One',
  chapter_number: 1,
  page: 42,
  text: 'The map is not the territory.',
  datetime: '2026-01-01T00:00:00',
  tags: [],
  flashcards: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

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

/**
 * Highlights sitting in no chapter are absent from the tree but present in
 * `highlight_count`, so a test that needs them sets the count explicitly.
 */
export const aBookDetails = (overrides: Partial<BookDetails> = {}): BookDetails => {
  const book = {
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
  };
  return {
    ...book,
    highlight_count:
      overrides.highlight_count ??
      book.chapters.reduce((sum, chapter) => sum + chapter.highlights.length, 0),
  };
};

export const aBookCard = (
  overrides: Partial<BookWithHighlightCount> = {}
): BookWithHighlightCount => ({
  id: 1,
  title: 'The Pragmatic Reader',
  author: 'Ada Lovelace',
  isbn: null,
  cover_file: null,
  cover_blurhash: null,
  highlight_count: 0,
  flashcard_count: 0,
  note_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});
