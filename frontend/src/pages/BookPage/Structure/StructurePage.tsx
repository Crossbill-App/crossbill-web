import { useGetBookDigest } from '@/api/generated/digest/digest';
import type {
  ChapterDigestResponse,
  ChapterWithHighlights,
  PositionResponse,
} from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { useUrlEntityDialog } from '@/components/dialogs/useUrlEntityDialog.ts';
import { PageHeader } from '@/components/layout/PageHeader.tsx';
import { SemanticSearchField } from '@/components/search/SemanticSearchField.tsx';
import { useSemanticSearch } from '@/components/search/useSemanticSearch.ts';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { useBookTabFilters } from '@/pages/BookPage/common/useBookTabFilters.ts';
import { BOOK_PAGE_LABELS } from '@/pages/BookPage/navigation/bookPageRoutes.ts';
import { Alert } from '@mui/material';
import { keyBy } from 'lodash';
import { useMemo } from 'react';
import { BatchDigestToolbar } from './BatchDigestToolbar';
import { ChapterAccordion } from './ChapterAccordion';
import { ChapterDetailDialog } from './ChapterDetailDialog/ChapterDetailDialog.tsx';
import { chapterMatchesFromDigests } from './chapterMatches.ts';

/**
 * Chapter ids along the reading-position path, walked once over *unfiltered*
 * document order. A search filters and re-sorts `childrenByParentId` by
 * score, so deriving "current" from that map (e.g. by peeking at the next
 * rendered sibling) would put the indicator on whichever chapter happens to
 * render next rather than the next chapter in the book. At each level the
 * current chapter is the one that is read while its next document-order
 * sibling is not; its children are then walked the same way.
 */
const currentChapterIdsAlongReadingPath = (
  childrenByParentId: Map<number | null, ChapterWithHighlights[]>,
  readingPosition: PositionResponse | null | undefined
): Set<number> => {
  const ids = new Set<number>();
  if (!readingPosition) return ids;

  const isRead = (chapter: ChapterWithHighlights) =>
    chapter.start_position != null && readingPosition.index >= chapter.start_position.index;

  let parentId: number | null = null;
  for (;;) {
    const siblings: ChapterWithHighlights[] = childrenByParentId.get(parentId) ?? [];
    const current: ChapterWithHighlights | undefined = siblings.find(
      (chapter, index) => isRead(chapter) && !(siblings[index + 1] && isRead(siblings[index + 1]))
    );
    if (!current) break;
    ids.add(current.id);
    parentId = current.id;
  }
  return ids;
};

export const StructurePage = () => {
  const { book } = useBookPage();

  const { data: bookDigest } = useGetBookDigest(book.id);

  const digestByChapterId = useMemo(() => {
    const map: Record<number, ChapterDigestResponse> = {};
    if (bookDigest?.items) {
      for (const item of bookDigest.items) {
        map[item.chapter_id] = item;
      }
    }
    return map;
  }, [bookDigest]);

  const eligibleChapterIds = useMemo(
    () =>
      new Set(
        book.chapters.filter((chapter) => chapter.start_position != null).map(({ id }) => id)
      ),
    [book.chapters]
  );

  const existingSummaryCount = bookDigest
    ? bookDigest.items.filter((digest) => eligibleChapterIds.has(digest.chapter_id)).length
    : undefined;

  const { data: gistNotes } = useGetNotesForBook(book.id, {
    kind: 'gist',
  });

  const gistByChapterId = useMemo(() => {
    const map = new Map<number, string>();
    for (const note of gistNotes?.items ?? []) {
      if (note.chapter_ids.length === 0) continue;
      const chapterId = note.chapter_ids[0];
      if (!map.has(chapterId)) {
        map.set(chapterId, note.body);
      }
    }
    return map;
  }, [gistNotes]);

  // Unfiltered: the chapter dialog's Notes tab counts every note linked to the
  // chapter, gists included, and the row is meant to agree with it. Shares a
  // query key with the book header's own notes fetch, so it costs no request.
  const { data: allNotes } = useGetNotesForBook(book.id);

  const noteCountByChapterId = useMemo(() => {
    const map = new Map<number, number>();
    for (const note of allNotes?.items ?? []) {
      for (const chapterId of note.chapter_ids) {
        map.set(chapterId, (map.get(chapterId) ?? 0) + 1);
      }
    }
    return map;
  }, [allNotes]);

  const childrenByParentId = useMemo(() => {
    const map = new Map<number | null, ChapterWithHighlights[]>();
    for (const ch of book.chapters) {
      const key = ch.parent_id ?? null;
      const list = map.get(key) ?? [];
      list.push(ch);
      map.set(key, list);
    }
    return map;
  }, [book.chapters]);

  /**
   * Every chapter in document order, parents included.
   *
   * Parents are digestible on the backend — `EnqueueBookDigestsUseCase` takes
   * any chapter with a start position — so they own digests, embeddings and
   * highlights of their own, and semantic results link straight to them. A
   * leaves-only list left those links resolving to nothing at all.
   */
  const chaptersInDocumentOrder = useMemo(() => {
    const result: ChapterWithHighlights[] = [];
    const collect = (parentId: number | null) => {
      for (const ch of childrenByParentId.get(parentId) ?? []) {
        result.push(ch);
        collect(ch.id);
      }
    };
    collect(null);
    return result;
  }, [childrenByParentId]);

  const chapterDialog = useUrlEntityDialog<ChapterWithHighlights>({
    param: 'chapterId',
    items: chaptersInDocumentOrder,
  });

  // Compute bookmarks map
  const bookmarksByHighlightId = useMemo(
    () => keyBy(book.bookmarks, 'highlight_id'),
    [book.bookmarks]
  );

  const { searchText, handleSearch } = useBookTabFilters('/book/$bookId/structure');
  const search = useSemanticSearch({ query: searchText, bookId: book.id });

  const matches = useMemo(
    () =>
      search.results ? chapterMatchesFromDigests(search.results.digests, book.chapters) : null,
    [search.results, book.chapters]
  );

  // While a search is active, each parent keeps only its matching children,
  // ordered by their best descendant score. No search → the map is untouched.
  const visibleChildrenByParentId = useMemo(() => {
    if (!matches) return childrenByParentId;
    const map = new Map<number | null, ChapterWithHighlights[]>();
    for (const [parentId, children] of childrenByParentId) {
      const kept = children
        .filter((chapter) => matches.visibleIds.has(chapter.id))
        .sort(
          (a, b) => (matches.bestScoreById.get(b.id) ?? 0) - (matches.bestScoreById.get(a.id) ?? 0)
        );
      if (kept.length > 0) map.set(parentId, kept);
    }
    return map;
  }, [childrenByParentId, matches]);

  const readingPosition = book.reading_position;

  // Derived from the unfiltered tree so a search can never move the
  // current-chapter indicator (see the function's own doc comment).
  const currentChapterIds = useMemo(
    () => currentChapterIdsAlongReadingPath(childrenByParentId, readingPosition),
    [childrenByParentId, readingPosition]
  );

  const topLevelChapters = visibleChildrenByParentId.get(null) ?? [];

  return (
    <>
      <PageHeader
        title={BOOK_PAGE_LABELS.structure}
        search={
          <SemanticSearchField
            value={searchText}
            onChange={handleSearch}
            placeholder="Search chapters by meaning..."
          />
        }
        action={
          <BatchDigestToolbar
            bookId={book.id}
            eligibleChapterCount={eligibleChapterIds.size}
            existingSummaryCount={existingSummaryCount}
          />
        }
      />

      {search.isError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Search failed. Showing all chapters.
        </Alert>
      )}

      {book.chapters.length === 0 ? (
        <EmptyStateText variant="page">
          No chapter structure available for this book.
        </EmptyStateText>
      ) : search.hasQuery && topLevelChapters.length === 0 ? (
        <EmptyStateText variant="page">No chapters match “{searchText}”.</EmptyStateText>
      ) : (
        topLevelChapters.map((chapter) => (
          <ChapterAccordion
            // Keyed by the query so a new search remounts the branch and its
            // `expanded` state re-initialises from `preExpanded`.
            key={`${chapter.id}:${searchText}`}
            chapter={chapter}
            childrenByParentId={visibleChildrenByParentId}
            gistByChapterId={gistByChapterId}
            noteCountByChapterId={noteCountByChapterId}
            bookId={book.id}
            readingPosition={readingPosition}
            currentChapterIds={currentChapterIds}
            preExpanded={search.hasQuery}
            onChapterClick={chapterDialog.open}
          />
        ))
      )}

      {chapterDialog.activeItem && (
        <ChapterDetailDialog
          controller={chapterDialog}
          bookId={book.id}
          digestByChapterId={digestByChapterId}
          bookmarksByHighlightId={bookmarksByHighlightId}
          availableTags={book.tags}
          bookFlashcards={book.book_flashcards}
        />
      )}
    </>
  );
};
