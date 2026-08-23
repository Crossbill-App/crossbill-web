import {
  getGetBookDetailsQueryKey,
  getGetBooksQueryKey,
  getGetRecentlyViewedBooksQueryKey,
} from '@/api/generated/books/books.ts';
import { getGetBookDigestQueryKey } from '@/api/generated/digest/digest.ts';
import { getGetBookHighlightLabelsQueryKey } from '@/api/generated/highlight-labels/highlight-labels.ts';
import { getGetActiveBookDigestBatchQueryKey } from '@/api/generated/jobs/jobs.ts';
import { getGetNoteQueryKey, getGetNotesForBookQueryKey } from '@/api/generated/notes/notes.ts';
import {
  getGetActiveBackfillQueryKey,
  getRelatedContentQueryKey,
} from '@/api/generated/semantic/semantic.ts';
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

    const drop = (...keys: QueryKey[]) => {
      for (const queryKey of keys) {
        queryClient.removeQueries({ queryKey });
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
       * yet.
       */
      noteChanged: (bookId: number, noteId?: number) =>
        invalidate(
          getGetNotesForBookQueryKey(bookId),
          ...(noteId === undefined ? [] : [getGetNoteQueryKey(noteId)])
        ),

      /**
       * A note was hard-deleted. Its detail is dropped, not invalidated: on a
       * failed refetch React Query keeps the last data, so any other view
       * holding it would keep rendering the deleted note.
       */
      noteDeleted: (bookId: number, noteId: number) => {
        drop(getGetNoteQueryKey(noteId));
        invalidate(getGetNotesForBookQueryKey(bookId));
      },

      /**
       * A flashcard was created, edited or deleted.
       *
       * Cards are counted in book details wherever they came from. Pass `noteId`
       * for a card belonging to a note, whose detail embeds its own card list.
       *
       * The notes list embeds each note's cards too, and is refreshed whether or
       * not a `noteId` is given: a missed invalidation there shows up as a card
       * vanishing from a note when its dialog is reopened, which is far more
       * expensive than refetching one small list.
       */
      flashcardsChanged: (bookId: number, noteId?: number) =>
        invalidate(
          getGetBookDetailsQueryKey(bookId),
          getGetNotesForBookQueryKey(bookId),
          ...(noteId === undefined ? [] : [getGetNoteQueryKey(noteId)])
        ),

      /** Digest content was generated or answered for a chapter. */
      digestChanged: (bookId: number) =>
        invalidate(getGetBookDigestQueryKey(bookId), getRelatedContentQueryKey()),

      /** A batch digest job reached a terminal state, so its output is ready. */
      digestBatchFinished: (bookId: number) =>
        invalidate(getGetBookDigestQueryKey(bookId), getGetActiveBookDigestBatchQueryKey(bookId)),

      /** A batch digest job was cancelled; no new digest content exists. */
      digestBatchCancelled: (bookId: number) =>
        invalidate(getGetActiveBookDigestBatchQueryKey(bookId)),

      /**
       * The embedding backfill started, ended or was cancelled.
       *
       * One event rather than the digest batch's pair: nothing caches embedded
       * content — search is fetched on demand — so only the "is one running"
       * query is ever affected.
       */
      embeddingBackfillChanged: () => invalidate(getGetActiveBackfillQueryKey()),

      /** A highlight label was renamed or recoloured. Book details embeds labels. */
      highlightLabelsChanged: (bookId: number) =>
        invalidate(getGetBookDetailsQueryKey(bookId), getGetBookHighlightLabelsQueryKey(bookId)),
    };
  }, [queryClient]);
};
