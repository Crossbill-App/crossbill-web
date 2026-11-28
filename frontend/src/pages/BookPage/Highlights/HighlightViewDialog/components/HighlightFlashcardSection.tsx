import { useGetHighlightFlashcardSuggestions } from '@/api/generated/flashcards/flashcards.ts';
import type { Highlight } from '@/api/generated/model';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { FlashcardSection } from '@/components/features/flashcards/FlashcardSection.tsx';
import { sortBy } from 'lodash';

interface HighlightFlashcardSectionProps {
  highlight: Highlight;
  bookId: number;
  disabled?: boolean;
}

export const HighlightFlashcardSection = ({
  highlight,
  bookId,
  disabled = false,
}: HighlightFlashcardSectionProps) => {
  const { refetch } = useGetHighlightFlashcardSuggestions(highlight.id, {
    query: { enabled: false },
  });

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
      source={{ kind: 'highlight', highlight }}
      disabled={disabled}
      fetchSuggestions={refetch}
    />
  );
};
