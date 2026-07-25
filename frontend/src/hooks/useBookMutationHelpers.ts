import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useCacheEvents } from '@/lib/cacheEvents.ts';

/**
 * Shared feedback + cache-invalidation helpers for book-scoped mutations.
 *
 * Dedupes the hand-rolled `console.error(...) + showSnackbar('Failed to ...')`
 * onError blocks that were pasted across the book feature tabs.
 *
 * The two invalidation helpers now delegate to `useCacheEvents`, which owns the
 * query keys. They are kept as a thin shim so existing callers keep working;
 * new code should use `useCacheEvents` directly, and the callers here move over
 * as they are touched.
 */
export const useBookMutationHelpers = (bookId: number) => {
  const { showSnackbar } = useSnackbar();
  const cache = useCacheEvents();

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

  /** @deprecated Use `useCacheEvents().bookChanged(bookId)`. */
  const invalidateBookDetails = () => cache.bookChanged(bookId);

  /** @deprecated Use `useCacheEvents().tagsChanged(bookId)`. */
  const invalidateBookAndTags = () => cache.tagsChanged(bookId);

  return { mutationErrorHandler, invalidateBookDetails, invalidateBookAndTags };
};
