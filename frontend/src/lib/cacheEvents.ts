import {
  getGetBookDetailsQueryKey,
  getGetBooksQueryKey,
  getGetRecentlyViewedBooksQueryKey,
} from '@/api/generated/books/books.ts';
import { getGetBookHighlightLabelsQueryKey } from '@/api/generated/highlight-labels/highlight-labels.ts';
import { getGetActiveBookPrereadingBatchQueryKey } from '@/api/generated/jobs/jobs.ts';
import { getGetNoteQueryKey, getGetNotesForBookQueryKey } from '@/api/generated/notes/notes.ts';
import { getGetBookPrereadingQueryKey } from '@/api/generated/prereading/prereading.ts';
import { getGetTagsQueryKey } from '@/api/generated/tags/tags.ts';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { useMemo } from 'react';

/**
 * Cache invalidation expressed as domain events rather than query keys.
 *
 * Mutations say what changed — `noteChanged`, `tagsChanged` — and this module
 * decides which queries that invalidates. Callers do not name query keys, so
 * the set of queries affected by a change lives in one place instead of being
 * restated, and diverging, at each mutation site.
 *
 * Keys always come from the generated getters. A hand-written key silently
 * matched nothing for months (see the books list after deleting a book), which
 * is the failure this module exists to make unrepeatable.
 *
 * Not for optimistic updates, cache seeding or write-through: those legitimately
 * reach for `setQueryData` at their call site, and describing them as events
 * would misrepresent what they do.
 */
export const useCacheEvents = () => {
  const queryClient = useQueryClient();

  return useMemo(() => {
    const invalidate = (...keys: QueryKey[]) => {
      for (const queryKey of keys) {
        void queryClient.invalidateQueries({ queryKey });
      }
    };

    return {
      /** A book's own record changed — title, reading stage, cover, highlights. */
      bookChanged: (bookId: number) => invalidate(getGetBookDetailsQueryKey(bookId)),

      /** A book was opened, which reorders the recently-viewed list. */
      bookViewed: () => invalidate(getGetRecentlyViewedBooksQueryKey()),

      /** A book was added or removed, so every listing of books is affected. */
      booksListChanged: () =>
        invalidate(getGetBooksQueryKey(), getGetRecentlyViewedBooksQueryKey()),

      /** A tag or tag group changed. Book details carries the book's tag list too. */
      tagsChanged: (bookId: number) =>
        invalidate(getGetBookDetailsQueryKey(bookId), getGetTagsQueryKey(bookId)),

      /**
       * A note was created, edited, or had its links changed.
       *
       * Pass `noteId` when the note already exists, so the open detail view
       * refreshes too. Omit it after creating a note, whose detail is not cached
       * yet, and after deleting one, whose detail would refetch into a 404.
       */
      noteChanged: (bookId: number, noteId?: number) =>
        invalidate(
          getGetNotesForBookQueryKey(bookId),
          ...(noteId === undefined ? [] : [getGetNoteQueryKey(noteId)])
        ),

      /**
       * A flashcard was created, edited or deleted.
       *
       * Cards are counted in book details wherever they came from. Pass `noteId`
       * for a card belonging to a note, whose detail embeds its own card list.
       * Highlight- and chapter-sourced cards need no second key: their views read
       * from book details.
       */
      flashcardsChanged: (bookId: number, noteId?: number) =>
        invalidate(
          getGetBookDetailsQueryKey(bookId),
          ...(noteId === undefined ? [] : [getGetNoteQueryKey(noteId)])
        ),

      /** Prereading content was generated or answered for a chapter. */
      prereadingChanged: (bookId: number) => invalidate(getGetBookPrereadingQueryKey(bookId)),

      /** A batch prereading job reached a terminal state, so its output is ready. */
      prereadingBatchFinished: (bookId: number) =>
        invalidate(
          getGetBookPrereadingQueryKey(bookId),
          getGetActiveBookPrereadingBatchQueryKey(bookId)
        ),

      /** A batch prereading job was cancelled; no new prereading content exists. */
      prereadingBatchCancelled: (bookId: number) =>
        invalidate(getGetActiveBookPrereadingBatchQueryKey(bookId)),

      /** A highlight label was renamed or recoloured. Book details embeds labels. */
      highlightLabelsChanged: (bookId: number) =>
        invalidate(getGetBookDetailsQueryKey(bookId), getGetBookHighlightLabelsQueryKey(bookId)),
    };
  }, [queryClient]);
};
