import type { ReadingSession } from '@/api/generated/model';
import { formatDate, formatDuration, formatTime } from '@/utils/date.ts';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface SessionCardProps {
  session: ReadingSession;
}

/**
 * One reading session in the sessions list: when it happened, which pages it
 * covered and how long it ran.
 *
 * Padded like the other list cards so the rows line up. Nothing here is clickable yet, so the card is a plain `Box` rather than the
 * hoverable action area: a button that opens nothing would promise a detail
 * view the tab does not have.
 */
export const SessionCard = ({ session }: SessionCardProps) => {
  const { t } = useTranslation();
  const { start_page: startPage, end_page: endPage } = session;
  const hasPageRange = startPage != null && endPage != null;

  return (
    <Box sx={{ px: 2.5, py: 1 }}>
      <Typography variant="h3" sx={{ mb: 0.5 }}>
        {t('book.statistics.sessionCard.title', {
          date: formatDate(session.start_time),
          time: formatTime(session.start_time),
        })}
      </Typography>

      {hasPageRange && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {t('book.statistics.sessionCard.pages', { start: startPage, end: endPage })}
        </Typography>
      )}
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        {t('book.statistics.sessionCard.duration', {
          duration: formatDuration(session.start_time, session.end_time),
        })}
      </Typography>
    </Box>
  );
};
