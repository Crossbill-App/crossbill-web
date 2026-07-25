import { getGetBookDetailsQueryKey } from '@/api/generated/books/books.ts';
import { getGetTagsQueryKey } from '@/api/generated/tags/tags.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useQueryClient } from '@tanstack/react-query';

/**
 * Shared feedback + cache-invalidation helpers for book-scoped mutations.
 *
 * Dedupes the hand-rolled `console.error(...) + showSnackbar('Failed to ...')`
 * onError blocks and the "invalidate book details (+ tags)" invalidation pairs
 * that were pasted across the book feature tabs. Caching strategies themselves
 * are intentionally left with their call sites.
 */
export const useBookMutationHelpers = (bookId: number) => {
  const queryClient = useQueryClient();
  const { showSnackbar } = useSnackbar();

  /**
   * Build a mutation `onError` handler that logs the failure and shows the
   * standard "Failed to {action}. Please try again." error snackbar.
   *
   * @example
   * ```ts
   * onError: mutationErrorHandler('delete highlight'),
   * ```
   */
  const mutationErrorHandler = (actionLabel: string) => (error: unknown) => {
    console.error(`Failed to ${actionLabel}:`, error);
    showSnackbar(`Failed to ${actionLabel}. Please try again.`, 'error');
  };

  /** Invalidate the book details query. */
  const invalidateBookDetails = () => {
    void queryClient.invalidateQueries({
      queryKey: getGetBookDetailsQueryKey(bookId),
    });
  };

  /** Invalidate the book details query and the book's tags query. */
  const invalidateBookAndTags = () => {
    invalidateBookDetails();
    void queryClient.invalidateQueries({
      queryKey: getGetTagsQueryKey(bookId),
    });
  };

  return { mutationErrorHandler, invalidateBookDetails, invalidateBookAndTags };
};
