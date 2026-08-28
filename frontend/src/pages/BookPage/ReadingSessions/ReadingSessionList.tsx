import type { Bookmark, ReadingSession } from '@/api/generated/model';
import { FadeInOut } from '@/components/animations/FadeInOut';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { Box } from '@mui/material';
import { ReadingSessionCard } from './ReadingSessionCard';

interface ReadingSessionListProps {
  sessions: ReadingSession[];
  emptyMessage?: string;
  animationKey?: string;
  bookmarksByHighlightId: Record<number, Bookmark>;
  onOpenHighlight: (sessionId: number, highlightId: number) => void;
}

export const ReadingSessionList = ({
  sessions,
  emptyMessage = 'No reading sessions recorded yet.',
  animationKey = 'reading-sessions',
  bookmarksByHighlightId,
  onOpenHighlight,
}: ReadingSessionListProps) => {
  return (
    <FadeInOut ekey={animationKey}>
      {sessions.length === 0 ? (
        <EmptyStateText variant="page">{emptyMessage}</EmptyStateText>
      ) : (
        <Box
          component="ul"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            listStyle: 'none',
            p: 0,
            m: 0,
          }}
          aria-label="Reading sessions"
        >
          {sessions.map((session) => (
            <ReadingSessionCard
              key={session.id}
              session={session}
              bookmarksByHighlightId={bookmarksByHighlightId}
              onOpenHighlight={onOpenHighlight}
            />
          ))}
        </Box>
      )}
    </FadeInOut>
  );
};
