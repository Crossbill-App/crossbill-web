import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();

  return (actionLabel: string) => (error: unknown) => {
    console.error(`Failed to ${actionLabel}:`, error);
    showSnackbar(t('components.mutationErrorHandler.message', { action: actionLabel }), 'error');
  };
};
