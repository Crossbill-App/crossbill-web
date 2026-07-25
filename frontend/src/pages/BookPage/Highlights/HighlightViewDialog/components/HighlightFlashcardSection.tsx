import {
  useCreateFlashcardForHighlight,
  useGetHighlightFlashcardSuggestions,
} from '@/api/generated/flashcards/flashcards.ts';
import type { Highlight } from '@/api/generated/model';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { FlashcardSection } from '@/components/features/flashcards/FlashcardSection.tsx';
import { useAIFlashcardSuggestions } from '@/pages/BookPage/Flashcards/hooks/useAIFlashcardSuggestions.ts';
import { useFlashcardMutations } from '@/pages/BookPage/Flashcards/hooks/useFlashcardMutations.ts';
import { sortBy } from 'lodash';

interface HighlightFlashcardSectionProps {
  highlight: Highlight;
  bookId: number;
  disabled?: boolean;
}

/**
 * Wires the shared FlashcardSection to a highlight's cards and endpoints.
 * Rendered inside the highlight dialog's Flashcards tab, so it is always visible.
 */
export const HighlightFlashcardSection = ({
  highlight,
  bookId,
  disabled = false,
}: HighlightFlashcardSectionProps) => {
  const createFlashcardMutation = useCreateFlashcardForHighlight();
  const { isProcessing, saveFlashcard, updateFlashcard } = useFlashcardMutations({
    bookId,
    createFlashcard: (question, answer) =>
      createFlashcardMutation.mutateAsync({
        highlightId: highlight.id,
        data: { question, answer },
      }),
  });

  const { refetch } = useGetHighlightFlashcardSuggestions(highlight.id, {
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
    highlight.flashcards.map((flashcard) => ({
      ...flashcard,
      highlight,
      chapterName: highlight.chapter || '',
      chapterId: highlight.chapter_id || 0,
      tags: highlight.tags,
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
    />
  );
};
