import type { BookDetails } from '@/api/generated/model';
import { useGetBookReadingSessions } from '@/api/generated/reading-sessions/reading-sessions';
import { formatDate } from '@/utils/date';
import { Box, Typography } from '@mui/material';

interface BookStatsStripProps {
  book: BookDetails;
}

export const BookStatsStrip = ({ book }: BookStatsStripProps) => {
  const { data: sessionsData } = useGetBookReadingSessions(book.id, { limit: 1 });

  // Count highlights across all chapters
  const highlightCount = book.chapters.reduce((sum, chapter) => sum + chapter.highlights.length, 0);

  // Count flashcards
  const flashcardCount = book.book_flashcards?.length ?? 0;

  // Last read date from latest session
  const latestSession = sessionsData?.items[0];
  const lastReadDate = latestSession ? formatDate(latestSession.start_time) : null;

  const items = [
    book.page_count ? `${book.page_count} pages` : null,
    `${highlightCount} highlights`,
    `${flashcardCount} flashcards`,
    `Added ${formatDate(book.created_at)}`,
    lastReadDate ? `Last read ${lastReadDate}` : null,
  ].filter(Boolean);

  return (
    <Typography
      variant="body2"
      sx={{
        color: 'text.secondary',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: {
          xs: 'center',
          lg: 'left',
        },
        gap: 0.5,
        mt: 'auto',
        mb: 2,
        width: '100%',
      }}
    >
      {items.map((item, i) => (
        <Box
          component="span"
          key={i}
          sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
        >
          {i > 0 && (
            <Box component="span" sx={{ color: 'text.disabled' }}>
              ·
            </Box>
          )}
          {item}
        </Box>
      ))}
    </Typography>
  );
};
