import { useUpdateFlashcard } from '@/api/generated/flashcards/flashcards.ts';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface UseFlashcardMutationsOptions {
  bookId: number;
  /** Source-specific create call (e.g. POST to a highlight's or note's flashcards). */
  createFlashcard: (question: string, answer: string) => Promise<unknown>;
  /** Set when the cards belong to a note, whose detail embeds its own card list. */
  noteId?: number;
}

/**
 * Save/update mutations for flashcards shown in an entity view modal.
 * Update goes through the source-agnostic PUT /flashcards/:id endpoint;
 * create is delegated to the caller since it is source-specific.
 */
export const useFlashcardMutations = ({
  bookId,
  createFlashcard,
  noteId,
}: UseFlashcardMutationsOptions) => {
  const { t } = useTranslation();
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const [isProcessing, setIsProcessing] = useState(false);

  const invalidateFlashcardQueries = () => cache.flashcardsChanged(bookId, noteId);

  const updateFlashcardMutation = useUpdateFlashcard({
    mutation: {
      onSuccess: invalidateFlashcardQueries,
      onError: mutationErrorHandler(t('flashcards.errorActions.update')),
    },
  });

  const saveFlashcard = async (question: string, answer: string): Promise<boolean> => {
    if (!question.trim() || !answer.trim()) return false;

    setIsProcessing(true);
    try {
      await createFlashcard(question.trim(), answer.trim());
      invalidateFlashcardQueries();
      return true;
    } catch (error) {
      mutationErrorHandler(t('flashcards.errorActions.create'))(error);
      return false;
    } finally {
      setIsProcessing(false);
    }
  };

  const updateFlashcard = async (
    flashcardId: number,
    question: string,
    answer: string
  ): Promise<boolean> => {
    if (!question.trim() || !answer.trim()) return false;

    setIsProcessing(true);
    try {
      await updateFlashcardMutation.mutateAsync({
        flashcardId,
        data: { question: question.trim(), answer: answer.trim() },
      });
      return true;
    } catch {
      // Already reported via the mutation's onError
      return false;
    } finally {
      setIsProcessing(false);
    }
  };

  return { isProcessing, saveFlashcard, updateFlashcard };
};
