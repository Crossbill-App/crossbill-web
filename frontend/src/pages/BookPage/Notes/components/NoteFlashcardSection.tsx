import {
  useCreateFlashcardForNote,
  useGetNoteFlashcardSuggestions,
} from '@/api/generated/flashcards/flashcards.ts';
import type { NoteWithLinks } from '@/api/generated/model';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { FlashcardSection } from '@/components/features/flashcards/FlashcardSection.tsx';
import { useAIFlashcardSuggestions } from '@/pages/BookPage/Flashcards/hooks/useAIFlashcardSuggestions.ts';
import { useFlashcardMutations } from '@/pages/BookPage/Flashcards/hooks/useFlashcardMutations.ts';
import { sortBy } from 'lodash';

interface NoteFlashcardSectionProps {
  note: NoteWithLinks;
  bookId: number;
  disabled?: boolean;
}

/**
 * Wires the shared FlashcardSection to a note's cards and endpoints. Rendered
 * inside the note dialog's Flashcards tab, so it is always visible.
 */
export const NoteFlashcardSection = ({
  note,
  bookId,
  disabled = false,
}: NoteFlashcardSectionProps) => {
  const createFlashcardMutation = useCreateFlashcardForNote();
  const { isProcessing, saveFlashcard, updateFlashcard } = useFlashcardMutations({
    bookId,
    noteId: note.id,
    createFlashcard: (question, answer) =>
      createFlashcardMutation.mutateAsync({
        noteId: note.id,
        // The note may link several books; file the card under the one being viewed
        data: { question, answer, book_id: bookId },
      }),
  });

  const { refetch } = useGetNoteFlashcardSuggestions(note.id, {
    query: {
      enabled: false,
    },
  });
  const { isLoading, suggestions, fetchSuggestions, removeSuggestion } = useAIFlashcardSuggestions(
    async () => {
      const result = await refetch();
      if (result.error) throw result.error;
      return result.data;
    }
  );

  const flashcardsWithContext: FlashcardWithContext[] = sortBy(
    (note.flashcards ?? []).map((flashcard) => ({
      ...flashcard,
      highlight: null,
      chapterName: '',
      chapterId: flashcard.chapter_id ?? null,
      tags: [],
    })),
    (f) => f.question.toLowerCase()
  );

  return (
    <FlashcardSection
      flashcards={flashcardsWithContext}
      bookId={bookId}
      disabled={disabled}
      isProcessing={isProcessing}
      onSaveFlashcard={saveFlashcard}
      onUpdateFlashcard={updateFlashcard}
      suggestions={suggestions}
      suggestionsLoading={isLoading}
      onFetchSuggestions={fetchSuggestions}
      onRemoveSuggestion={removeSuggestion}
      noteId={note.id}
    />
  );
};
