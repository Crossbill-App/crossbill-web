import type {
  BookSearchItem,
  DigestSearchItem,
  GlobalSearchResults,
  HighlightSearchItem,
  NoteSearchItem,
  SemanticSearchResults,
} from '@/api/generated/model';
import { linkOptions } from '@tanstack/react-router';

type GlobalSearchRowType = 'highlight' | 'note' | 'chapter' | 'book';

export interface GlobalSearchRow {
  key: string;
  type: GlobalSearchRowType;
  /** Cosine similarity, or null for a book: a name match is not a ranking. */
  score: number | null;
  id: number;
  bookId: number;
  title: string | null;
  text: string;
  bookTitle: string;
  chapterLabel: string | null;
  coverFile: string | null;
  coverBlurhash: string | null;
}

/** A row the endpoint scored, and so one the merged ranking can order. */
type RankedSearchRow = GlobalSearchRow & { score: number };

export const MAX_GLOBAL_SEARCH_ROWS = 10;

/** What a row's type is called wherever one is labelled to the reader. */
export const SEARCH_ROW_TYPE_LABELS: Record<GlobalSearchRowType, string> = {
  highlight: 'Highlight',
  note: 'Note',
  chapter: 'Chapter',
  book: 'Book',
};

const highlightRows = (hits: HighlightSearchItem[]): RankedSearchRow[] =>
  hits.map((hit) => ({
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

/**
 * Notes with no linked book are dropped: their row would have no cover and no
 * page to open, since a note view only exists inside a book. They stay
 * invisible until a global note view exists.
 */
const noteRows = (hits: NoteSearchItem[]): RankedSearchRow[] =>
  hits.flatMap((hit) => {
    // `books[0]` is untyped as optional (noUncheckedIndexedAccess is off), so
    // the emptiness check is on `.length`, not on `book` itself.
    if (hit.books.length === 0) return [];
    const book = hit.books[0];
    return [
      {
        key: `note-${hit.id}`,
        type: 'note' as const,
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

/** A digest's row opens the chapter it summarises, not the digest itself. */
const digestRows = (hits: DigestSearchItem[]): RankedSearchRow[] =>
  hits.map((hit) => ({
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

/**
 * Books matched by their own title or author. The author rides on
 * `chapterLabel` because that is the field the metadata line renders, and a
 * book has no chapter to put there.
 */
const bookRows = (hits: BookSearchItem[]): GlobalSearchRow[] =>
  hits.map((hit) => ({
    key: `book-${hit.id}`,
    type: 'book',
    score: null,
    id: hit.id,
    bookId: hit.id,
    title: hit.title,
    text: '',
    bookTitle: hit.title,
    chapterLabel: hit.author,
    coverFile: hit.cover_file,
    coverBlurhash: hit.cover_blurhash,
  }));

/**
 * Flattens the endpoint's three scored groups into one list ranked by score.
 *
 * Scores are cosine similarity on one scale for all three types, which is what
 * makes a merged ranking meaningful rather than a presentation trick. Both
 * readers of the endpoint show one list: three lists side by side make the
 * reader compare scores the ranking has already compared.
 */
export const mergeSearchRows = (results: SemanticSearchResults | undefined): GlobalSearchRow[] => {
  if (!results) return [];

  return [
    ...highlightRows(results.highlights),
    ...noteRows(results.notes),
    ...digestRows(results.digests),
  ].sort((a, b) => b.score - a.score);
};

/**
 * Books on top, then the merged ranking cut to what the dropdown has room for.
 *
 * A book carries no score, so it cannot be ranked against the rest; it also
 * needs no defending, since a reader who types a title wants the book itself.
 * The endpoint caps the books, so the list stays short without a cap here.
 */
export const toGlobalSearchRows = (results: GlobalSearchResults | undefined): GlobalSearchRow[] =>
  results
    ? [...bookRows(results.books), ...mergeSearchRows(results).slice(0, MAX_GLOBAL_SEARCH_ROWS)]
    : [];

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
    // The book's landing page: `/book/$bookId` only redirects here.
    case 'book':
      return linkOptions({ to: '/book/$bookId/structure', params });
  }
};
