import { useSetFlashcardStatus } from '@/api/generated/flashcards/flashcards.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useTranslation } from 'react-i18next';

interface UseFlashcardUnsuspendOptions {
  bookId: number;
  noteId?: number;
}

export const useFlashcardUnsuspend = ({ bookId, noteId }: UseFlashcardUnsuspendOptions) => {
  const { t } = useTranslation();
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();

  const mutation = useSetFlashcardStatus({
    mutation: {
      onSuccess: () => cache.flashcardsChanged(bookId, noteId),
      onError: mutationErrorHandler(t('flashcards.errors.unsuspend')),
    },
  });

  return {
    unsuspend: (flashcardId: number) =>
      mutation.mutate({ flashcardId, data: { status: 'active' } }),
    isUnsuspending: mutation.isPending,
  };
};
