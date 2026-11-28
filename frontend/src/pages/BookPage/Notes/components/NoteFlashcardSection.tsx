import { useGetNoteFlashcardSuggestions } from '@/api/generated/flashcards/flashcards.ts';
import type { NoteWithLinks } from '@/api/generated/model';
import type { FlashcardWithContext } from '@/components/features/flashcards/FlashcardChapterList.tsx';
import { FlashcardSection } from '@/pages/BookPage/Flashcards/FlashcardSection.tsx';
import { sortBy } from 'lodash';

interface NoteFlashcardSectionProps {
  note: NoteWithLinks;
  bookId: number;
  disabled?: boolean;
}

export const NoteFlashcardSection = ({
  note,
  bookId,
  disabled = false,
}: NoteFlashcardSectionProps) => {
  const { refetch } = useGetNoteFlashcardSuggestions(note.id, {
    query: { enabled: false },
  });

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
      source={{ kind: 'note', noteId: note.id }}
      disabled={disabled}
      refetchSuggestions={refetch}
    />
  );
};
