import {
  useCreateFlashcardForBook,
  useCreateFlashcardForHighlight,
  useCreateFlashcardForNote,
} from '@/api/generated/flashcards/flashcards.ts';
import type { Highlight } from '@/api/generated/model';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useTranslation } from 'react-i18next';

export type FlashcardSource =
  | { kind: 'highlight'; highlight: Highlight }
  | { kind: 'note'; noteId: number }
  | { kind: 'chapter'; chapterId: number }
  | { kind: 'book' };

export interface FlashcardContent {
  question: string;
  answer: string;
}

export const sourceNoteId = (source: FlashcardSource) =>
  source.kind === 'note' ? source.noteId : undefined;

export const useCreateFlashcard = (bookId: number) => {
  const { t } = useTranslation();
  const cache = useCacheEvents();
  const mutationErrorHandler = useMutationErrorHandler();
  const options = { mutation: { onError: mutationErrorHandler(t('flashcards.errors.create')) } };
  const forHighlight = useCreateFlashcardForHighlight(options);
  const forNote = useCreateFlashcardForNote(options);
  const forBook = useCreateFlashcardForBook(options);

  const send = (source: FlashcardSource, data: FlashcardContent) => {
    switch (source.kind) {
      case 'highlight':
        return forHighlight.mutateAsync({ highlightId: source.highlight.id, data });
      case 'note':
        // A note may link several books; file the card under the one being viewed.
        return forNote.mutateAsync({ noteId: source.noteId, data: { ...data, book_id: bookId } });
      case 'chapter':
        return forBook.mutateAsync({ bookId, data: { ...data, chapter_id: source.chapterId } });
      case 'book':
        return forBook.mutateAsync({ bookId, data });
    }
  };

  const createFlashcard = async (
    source: FlashcardSource,
    { question, answer }: FlashcardContent
  ): Promise<boolean> => {
    try {
      await send(source, { question: question.trim(), answer: answer.trim() });
    } catch {
      return false;
    }
    cache.flashcardsChanged(bookId, sourceNoteId(source));
    return true;
  };

  return {
    createFlashcard,
    isPending: forHighlight.isPending || forNote.isPending || forBook.isPending,
  };
};
