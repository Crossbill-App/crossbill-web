import { useSnackbar } from '@/context/SnackbarContext.tsx';

/**
 * Standard failure feedback for mutations: log the error and show the given
 * message in an error snackbar.
 *
 * The message is a whole translated sentence, never an action phrase spliced
 * into a shared template: word order and grammar around the verb differ by
 * language, so a translator needs the full sentence.
 *
 * @example
 * ```ts
 * onError: mutationErrorHandler(t('highlights.viewDialog.errors.deleteHighlight')),
 * ```
 */
export const useMutationErrorHandler = () => {
  const { showSnackbar } = useSnackbar();

  return (message: string) => (error: unknown) => {
    console.error(message, error);
    showSnackbar(message, 'error');
  };
};
