import type { SemanticSearchResults } from '@/api/generated/model';
import { linkOptions } from '@tanstack/react-router';

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

/**
 * The DOM id a row's element carries. Shared by the row itself and by
 * `aria-activedescendant` on the listbox, so the two cannot drift apart.
 */
export const globalSearchRowDomId = (row: GlobalSearchRow) => `global-search-${row.key}`;

/**
 * Router props for a row, as a switch rather than strings on the row itself:
 * TanStack Router types `to` against the route tree, and a `to: string` field
 * would throw that away.
 *
 * Lives beside `GlobalSearchRow` rather than in the row component: it is a
 * pure function of the row, and both `GlobalSearchResultRow` (click) and
 * `GlobalSearch` (Enter) need it, so it can't be component-local without
 * either duplicating it or exporting it from a component file — the latter
 * trips `react-refresh/only-export-components`.
 */
export const rowLinkProps = (row: GlobalSearchRow) => {
  const params = { bookId: String(row.bookId) };
  switch (row.type) {
    case 'highlight':
      return linkOptions({
        to: '/book/$bookId/highlights',
        params,
        search: { highlightId: row.id },
      });
    case 'note':
      return linkOptions({ to: '/book/$bookId/notes', params, search: { noteId: row.id } });
    case 'chapter':
      return linkOptions({
        to: '/book/$bookId/structure',
        params,
        search: { chapterId: row.id },
      });
  }
};
