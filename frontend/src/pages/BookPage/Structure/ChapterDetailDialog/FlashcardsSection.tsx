import {
  useCreateFlashcardForBook,
  useGetChapterFlashcardSuggestions,
} from '@/api/generated/flashcards/flashcards.ts';
import type {
  ChapterPrereadingResponse,
  ChapterWithHighlights,
  Flashcard,
  FlashcardSuggestionItem,
} from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { AIFeature } from '@/components/features/AIFeature.tsx';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import {
  CreateFlashcardForm,
  type FlashcardFormValues,
} from '@/pages/BookPage/Flashcards/CreateFlashcardForm.tsx';
import { FlashcardEditDialog } from '@/pages/BookPage/Flashcards/FlashcardEditDialog.tsx';
import { FlashcardListCard } from '@/pages/BookPage/Flashcards/FlashcardListCard.tsx';
import { FlashcardSuggestions } from '@/pages/BookPage/Flashcards/FlashcardSuggestions.tsx';
import { useFlashcardMutations } from '@/pages/BookPage/Flashcards/hooks/useFlashcardMutations.ts';
import { flatMap } from 'lodash';
import { useCallback, useMemo, useState } from 'react';

interface FlashcardsSectionProps {
  chapter: ChapterWithHighlights;
  bookId: number;
  prereadingSummary?: ChapterPrereadingResponse;
  bookFlashcards?: Flashcard[];
}

const useAIFlashcardSuggestions = (
  chapterId: number,
  showSnackbar: (message: string, severity: 'error' | 'warning' | 'info' | 'success') => void
) => {
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<FlashcardSuggestionItem[]>([]);

  const { refetch } = useGetChapterFlashcardSuggestions(chapterId, {
    query: {
      enabled: false,
    },
  });

  const fetchSuggestions = async () => {
    setIsLoading(true);
    try {
      const { data } = await refetch();
      if (data?.items) {
        setSuggestions(data.items);
      }
    } catch (error) {
      console.error('Failed to fetch flashcard suggestions:', error);
      showSnackbar('Failed to fetch suggestions. Please try again.', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const removeSuggestion = (index: number) => {
    setSuggestions((prev) => prev.filter((_, i) => i !== index));
  };

  return { isLoading, suggestions, fetchSuggestions, removeSuggestion };
};

export const FlashcardsSection = ({
  chapter,
  bookId,
  prereadingSummary,
  bookFlashcards,
}: FlashcardsSectionProps) => {
  const [editingFlashcard, setEditingFlashcard] = useState<FlashcardWithContext | null>(null);
  const { showSnackbar } = useSnackbar();
  const createFlashcardMutation = useCreateFlashcardForBook();
  const { isProcessing, saveFlashcard } = useFlashcardMutations({
    bookId,
    createFlashcard: (question, answer) =>
      createFlashcardMutation.mutateAsync({
        bookId,
        data: { question, answer, chapter_id: chapter.id },
      }),
  });
  const { isLoading, suggestions, fetchSuggestions, removeSuggestion } = useAIFlashcardSuggestions(
    chapter.id,
    showSnackbar
  );

  const flashcardsWithContext = useMemo((): FlashcardWithContext[] => {
    const highlightFlashcards = flatMap(chapter.highlights, (highlight) =>
      highlight.flashcards.map((flashcard) => ({
        ...flashcard,
        highlight,
        chapterName: chapter.name,
        chapterId: chapter.id,
        tags: highlight.tags,
      }))
    );

    const chapterLinkedFlashcards: FlashcardWithContext[] = (bookFlashcards ?? [])
      .filter((fc) => fc.chapter_id === chapter.id)
      .map((fc) => ({
        ...fc,
        highlight: null,
        chapterName: chapter.name,
        chapterId: chapter.id,
        tags: [],
      }));

    return [...highlightFlashcards, ...chapterLinkedFlashcards];
  }, [chapter, bookFlashcards]);

  const handleEditFlashcard = useCallback((flashcard: FlashcardWithContext) => {
    setEditingFlashcard(flashcard);
  }, []);

  const handleCloseEdit = useCallback(() => {
    setEditingFlashcard(null);
  }, []);

  const handleSave = (values: FlashcardFormValues) => saveFlashcard(values.question, values.answer);

  const handleAcceptSuggestion = async (suggestion: FlashcardSuggestionItem, index: number) => {
    const saved = await saveFlashcard(suggestion.question, suggestion.answer);
    if (saved) removeSuggestion(index);
  };

  return (
    <>
      {flashcardsWithContext.length > 0 && (
        <CardList sx={{ mb: 2 }}>
          {flashcardsWithContext.map((flashcard) => (
            <li key={flashcard.id}>
              <FlashcardListCard
                flashcard={flashcard}
                bookId={bookId}
                onEdit={() => handleEditFlashcard(flashcard)}
                showSourceHighlight={false}
              />
            </li>
          ))}
        </CardList>
      )}

      <CreateFlashcardForm
        editingFlashcardId={null}
        isDisabled={isProcessing}
        isProcessing={isProcessing}
        onSave={handleSave}
        onCancelEdit={() => {}}
      />

      {prereadingSummary && (
        <AIFeature>
          <FlashcardSuggestions
            suggestions={suggestions}
            isLoading={isLoading}
            disabled={false}
            onFetchSuggestions={fetchSuggestions}
            onAcceptSuggestion={handleAcceptSuggestion}
            onRejectSuggestion={removeSuggestion}
          />
        </AIFeature>
      )}

      {editingFlashcard && (
        <FlashcardEditDialog
          flashcard={editingFlashcard}
          bookId={bookId}
          open={true}
          onClose={handleCloseEdit}
        />
      )}
    </>
  );
};
