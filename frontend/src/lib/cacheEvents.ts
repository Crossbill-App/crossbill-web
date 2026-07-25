import { getGetBookDetailsQueryKey } from '@/api/generated/books/books.ts';
import { getGetNoteQueryKey, getGetNotesForBookQueryKey } from '@/api/generated/notes/notes.ts';
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
    };
  }, [queryClient]);
};
