import type { Flashcard, Highlight } from '@/api/generated/model';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { ChapterGroupedList } from '@/pages/BookPage/common/ChapterGroupedList.tsx';
import { FlashcardListCard } from '@/pages/BookPage/Flashcards/FlashcardListCard.tsx';
import type { ReactNode } from 'react';

export interface FlashcardWithContext extends Flashcard {
  highlight: Highlight | null;
  chapterName: string;
  chapterId: number | null;
  tags: { id: number; name: string }[];
}

export interface FlashcardChapterData {
  id: number;
  name: string;
  flashcards: FlashcardWithContext[];
  /** Accessible name for the group's list, where "Flashcards in <name>" does
   *  not read as English — the bucket for cards that are in no chapter. */
  listLabel?: string;
}

interface FlashcardChapterListProps {
  chapters: FlashcardChapterData[];
  bookId: number;
  isLoading?: boolean;
  emptyState?: ReactNode;
  animationKey?: string;
  onEditFlashcard: (flashcard: FlashcardWithContext) => void;
}

export const FlashcardChapterList = ({
  chapters,
  bookId,
  isLoading,
  emptyState = <EmptyStateText>No flashcards found.</EmptyStateText>,
  animationKey = 'flashcard-chapters',
  onEditFlashcard,
}: FlashcardChapterListProps) => (
  <ChapterGroupedList
    chapters={chapters}
    getChapterId={(chapter) => chapter.id}
    getChapterName={(chapter) => chapter.name}
    getItems={(chapter) => chapter.flashcards}
    getItemKey={(flashcard) => flashcard.id}
    ariaLabel={(chapter) => chapter.listLabel ?? `Flashcards in ${chapter.name}`}
    isLoading={isLoading}
    emptyState={emptyState}
    animationKey={animationKey}
    renderItem={(flashcard) => (
      <FlashcardListCard
        flashcard={flashcard}
        bookId={bookId}
        onEdit={() => onEditFlashcard(flashcard)}
      />
    )}
  />
);
