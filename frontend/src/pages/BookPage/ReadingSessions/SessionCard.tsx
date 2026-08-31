import type { ReadingSession } from '@/api/generated/model';
import { ReadingSessionIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { formatDate, formatDuration, formatTime } from '@/utils/date.ts';
import { Box, Stack, Typography } from '@mui/material';

interface SessionCardProps {
  session: ReadingSession;
}

/**
 * One reading session in the sessions list: when it happened, which pages it
 * covered and how long it ran.
 *
 * The left rail is the type marker the notes list uses, per B9 — sessions and
 * notes are both plain rows of a single kind, so they read as the same shape.
 * Nothing here is clickable yet, so the card is a plain `Box` rather than the
 * hoverable action area: a button that opens nothing would promise a detail
 * view the tab does not have.
 */
export const SessionCard = ({ session }: SessionCardProps) => {
  const { start_page: startPage, end_page: endPage } = session;
  const hasPageRange = startPage != null && endPage != null;

  return (
    <Box
      sx={{
        borderLeft: '3px solid',
        borderColor: 'primary.main',
        pl: 2,
        py: 1.5,
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
        <ReadingSessionIcon
          sx={{ fontSize: ICON_SIZE.ui, color: 'primary.main', opacity: 0.7, flexShrink: 0 }}
        />
        <Typography variant="h3">
          Session {formatDate(session.start_time)} {formatTime(session.start_time)}
        </Typography>
      </Stack>

      {/* Indented past the icon so both facts hang under the headline's text. */}
      <Box sx={{ pl: 3.5 }}>
        {hasPageRange && (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Pages {startPage} – {endPage}
          </Typography>
        )}
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Duration {formatDuration(session.start_time, session.end_time)}
        </Typography>
      </Box>
    </Box>
  );
};
