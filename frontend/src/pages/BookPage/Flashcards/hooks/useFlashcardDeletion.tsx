import { useDeleteFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import { ConfirmationDialog } from '@/components/dialogs/ConfirmationDialog.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface UseFlashcardDeletionOptions {
  bookId: number;
  noteId?: number;
  onDeleted?: () => void;
}

export const useFlashcardDeletion = ({
  bookId,
  noteId,
  onDeleted,
}: UseFlashcardDeletionOptions) => {
  const { t } = useTranslation();
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [pendingId, setPendingId] = useState<number | null>(null);

  const deleteMutation = useDeleteFlashcard({
    mutation: {
      onSuccess: () => {
        cache.flashcardsChanged(bookId, noteId);
        onDeleted?.();
      },
      onError: mutationErrorHandler(t('flashcards.errors.delete')),
    },
  });

  const handleConfirm = () => {
    if (pendingId !== null) deleteMutation.mutate({ flashcardId: pendingId });
    setPendingId(null);
  };

  const confirmation = (
    <ConfirmationDialog
      open={pendingId !== null}
      onClose={() => setPendingId(null)}
      onConfirm={handleConfirm}
      message={t('flashcards.shared.deleteConfirm')}
      confirmText={t('common.actions.delete')}
      confirmColor="error"
      isLoading={deleteMutation.isPending}
    />
  );

  return { requestDelete: setPendingId, isDeleting: deleteMutation.isPending, confirmation };
};
