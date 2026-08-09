import type { SemanticSearchResults } from '@/api/generated/model';

/** Not exported: consumers index `GlobalSearchRow['type']`, and knip fails CI
 *  on an export nothing imports. */
type GlobalSearchRowType = 'highlight' | 'note' | 'chapter';

export interface GlobalSearchRow {
  /**
   * React key. Content ids collide across types, and a digest's own id is not
   * the chapter id it opens, so both are folded in.
   */
  key: string;
  type: GlobalSearchRowType;
  score: number;
  /** The entity the row opens: a highlight, a note, or a chapter. */
  id: number;
  bookId: number;
  /** Bold single line above the text. Only notes have one. */
  title: string | null;
  /** Clamped to two lines by CSS, never truncated here. */
  text: string;
  bookTitle: string;
  chapterLabel: string | null;
  coverFile: string | null;
  coverBlurhash: string | null;
}

/** Rows in the app bar dropdown. A full results page will raise this. */
export const MAX_GLOBAL_SEARCH_ROWS = 10;

/**
 * Flattens the endpoint's three groups into one list ranked by score.
 *
 * Scores are cosine similarity on one scale for all three types, which is what
 * makes a merged ranking meaningful rather than a presentation trick.
 *
 * Notes with no linked book are dropped: their row would have no cover and no
 * page to open, since a note view only exists inside a book. They stay
 * invisible until a global note view exists.
 */
export const toGlobalSearchRows = (
  results: SemanticSearchResults | undefined
): GlobalSearchRow[] => {
  if (!results) return [];

  const highlights: GlobalSearchRow[] = results.highlights.map((hit) => ({
    key: `highlight-${hit.id}`,
    type: 'highlight',
    score: hit.score,
    id: hit.id,
    bookId: hit.book_id,
    title: null,
    text: hit.text,
    bookTitle: hit.book_title,
    chapterLabel: hit.chapter_name,
    coverFile: hit.cover_file,
    coverBlurhash: hit.cover_blurhash,
  }));

  const notes: GlobalSearchRow[] = results.notes.flatMap((hit) => {
    // `books[0]` is untyped as optional (noUncheckedIndexedAccess is off), so
    // the emptiness check is on `.length`, not on `book` itself.
    if (hit.books.length === 0) return [];
    const book = hit.books[0];
    return [
      {
        key: `note-${hit.id}`,
        type: 'note',
        score: hit.score,
        id: hit.id,
        bookId: book.id,
        title: hit.title,
        text: hit.body,
        bookTitle: book.title,
        chapterLabel: null,
        coverFile: book.cover_file,
        coverBlurhash: book.cover_blurhash,
      },
    ];
  });

  const chapters: GlobalSearchRow[] = results.digests.map((hit) => ({
    key: `digest-${hit.id}`,
    type: 'chapter',
    score: hit.score,
    id: hit.chapter_id,
    bookId: hit.book_id,
    title: null,
    text: hit.summary,
    bookTitle: hit.book_title,
    chapterLabel: hit.chapter_name,
    coverFile: hit.cover_file,
    coverBlurhash: hit.cover_blurhash,
  }));

  return [...highlights, ...notes, ...chapters]
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_GLOBAL_SEARCH_ROWS);
};
