import { useGetChapterFlashcardSuggestions } from '@/api/generated/flashcards/flashcards.ts';
import type {
  ChapterDigestResponse,
  ChapterWithHighlights,
  Flashcard,
} from '@/api/generated/model';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { FlashcardSection } from '@/components/features/flashcards/FlashcardSection.tsx';
import { flatMap } from 'lodash';
import { useMemo } from 'react';

interface FlashcardsSectionProps {
  chapter: ChapterWithHighlights;
  bookId: number;
  digestSummary?: ChapterDigestResponse;
  bookFlashcards?: Flashcard[];
}

export const FlashcardsSection = ({
  chapter,
  bookId,
  digestSummary,
  bookFlashcards,
}: FlashcardsSectionProps) => {
  const { refetch } = useGetChapterFlashcardSuggestions(chapter.id, {
    query: { enabled: false },
  });

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

  return (
    <FlashcardSection
      flashcards={flashcardsWithContext}
      bookId={bookId}
      source={{ kind: 'chapter', chapterId: chapter.id }}
      fetchSuggestions={digestSummary ? refetch : undefined}
    />
  );
};
