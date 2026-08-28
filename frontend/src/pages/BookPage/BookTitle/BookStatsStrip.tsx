import type { BookDetails } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { useGetBookReadingSessions } from '@/api/generated/reading-sessions/reading-sessions';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { DEFAULT_NOTE_KINDS, noteKindOf } from '@/pages/BookPage/Notes/noteKinds';
import { formatDate } from '@/utils/date';

interface BookStatsStripProps {
  book: BookDetails;
}

export const BookStatsStrip = ({ book }: BookStatsStripProps) => {
  const { data: sessionsData } = useGetBookReadingSessions(book.id, { limit: 1 });
  const { data: notesData } = useGetNotesForBook(book.id);

  // Count highlights across all chapters
  const highlightCount = book.chapters.reduce((sum, chapter) => sum + chapter.highlights.length, 0);

  // Count flashcards
  const flashcardCount = book.book_flashcards?.length ?? 0;

  // Gists are excluded so this matches what the Notes tab lists by default.
  const noteCount = (notesData?.items ?? []).filter((note) =>
    DEFAULT_NOTE_KINDS.includes(noteKindOf(note.kind))
  ).length;

  // Last read date from latest session
  const latestSession = sessionsData?.items[0];
  const lastReadDate = latestSession ? formatDate(latestSession.start_time) : null;

  const items = [
    book.page_count ? `${book.page_count} pages` : null,
    `${highlightCount} highlights`,
    `${noteCount} notes`,
    `${flashcardCount} flashcards`,
    `${sessionsData?.total ?? 0} sessions`,
    `Added ${formatDate(book.created_at)}`,
    lastReadDate ? `Last read ${lastReadDate}` : null,
  ].filter(Boolean);

  return (
    <MetadataRow
      items={items}
      sx={{
        textAlign: { xs: 'center', lg: 'left' },
        mt: 'auto',
        mb: 2,
        width: '100%',
      }}
    />
  );
};
