import type { Highlight } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { DialogTabs, type DialogTabItem } from '@/components/dialogs/DialogTabs.tsx';
import { LinkedNotesSection } from '@/pages/BookPage/Notes/components/LinkedNotesSection.tsx';
import { HighlightFlashcardSection } from './HighlightFlashcardSection.tsx';

interface HighlightTabsProps {
  highlight: Highlight;
  bookId: number;
  disabled?: boolean;
}

/**
 * Tabs for a highlight's secondary content: linked notes and flashcards —
 * mirroring the tabbed composition of `NoteViewDialog` and `ChapterDetailDialog`.
 */
export const HighlightTabs = ({ highlight, bookId, disabled = false }: HighlightTabsProps) => {
  const { data, isLoading } = useGetNotesForBook(bookId, {
    highlight_id: highlight.id,
  });
  // NOTE: the orval axios mutator unwraps the response (`.then(({ data }) => data)`),
  // so the generated GET hook's `data` is the payload itself, not an AxiosResponse.
  const notes = data?.items ?? [];

  const tabs: DialogTabItem[] = [
    {
      key: 'notes',
      label: 'Notes',
      count: notes.length,
      content: (
        <LinkedNotesSection
          bookId={bookId}
          target={{ kind: 'highlight', id: highlight.id, chapterId: highlight.chapter_id }}
          notes={notes}
          isLoading={isLoading}
          disabled={disabled}
        />
      ),
    },
    {
      key: 'flashcards',
      label: 'Flashcards',
      count: highlight.flashcards.length,
      content: (
        <HighlightFlashcardSection highlight={highlight} bookId={bookId} disabled={disabled} />
      ),
    },
  ];

  return <DialogTabs tabs={tabs} />;
};
