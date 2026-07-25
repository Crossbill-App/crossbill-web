import { useSnackbar } from '@/context/SnackbarContext.tsx';

/**
 * Standard failure feedback for mutations: log the error and show the
 * "Failed to {action}. Please try again." snackbar.
 *
 * @example
 * ```ts
 * onError: mutationErrorHandler('delete highlight'),
 * ```
 */
export const useMutationErrorHandler = () => {
  const { showSnackbar } = useSnackbar();

  return (actionLabel: string) => (error: unknown) => {
    console.error(`Failed to ${actionLabel}:`, error);
    showSnackbar(`Failed to ${actionLabel}. Please try again.`, 'error');
  };
};
