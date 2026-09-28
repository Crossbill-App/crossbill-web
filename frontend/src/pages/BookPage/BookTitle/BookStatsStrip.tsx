import type { BookDetails } from '@/api/generated/model';
import { useGetNotesForBook } from '@/api/generated/notes/notes.ts';
import { useGetBookReadingSessions } from '@/api/generated/reading-sessions/reading-sessions';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { DEFAULT_NOTE_KINDS, noteKindOf } from '@/pages/BookPage/Notes/noteKinds';
import { formatDate } from '@/utils/date';
import { useTranslation } from 'react-i18next';

interface BookStatsStripProps {
  book: BookDetails;
}

export const BookStatsStrip = ({ book }: BookStatsStripProps) => {
  const { t } = useTranslation();
  const { data: sessionsData } = useGetBookReadingSessions(book.id, { limit: 1 });
  const { data: notesData } = useGetNotesForBook(book.id);

  const flashcardCount = book.book_flashcards?.length ?? 0;

  // Gists are excluded so this matches what the Notes tab lists by default.
  const noteCount = (notesData?.items ?? []).filter((note) =>
    DEFAULT_NOTE_KINDS.includes(noteKindOf(note.kind))
  ).length;

  const latestSession = sessionsData?.items[0];
  const lastReadDate = latestSession ? formatDate(latestSession.start_time) : null;

  const items = [
    book.page_count ? t('common.counts.pages', { count: book.page_count }) : null,
    t('common.counts.highlights', { count: book.highlight_count ?? 0 }),
    t('common.counts.notes', { count: noteCount }),
    t('common.counts.flashcards', { count: flashcardCount }),
    t('common.counts.bookmarks', { count: book.bookmarks.length }),
    t('common.counts.sessions', { count: sessionsData?.total ?? 0 }),
    t('book.statsStrip.added', { date: formatDate(book.created_at) }),
    lastReadDate ? t('book.statsStrip.lastRead', { date: lastReadDate }) : null,
  ].filter(Boolean);

  return (
    <MetadataRow
      items={items}
      sx={{
        textAlign: 'left',
        mt: 'auto',
        mb: 2,
        width: '100%',
      }}
    />
  );
};
