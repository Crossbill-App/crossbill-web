import type { Bookmark, ReadingSession } from '@/api/generated/model';
import { CardList } from '@/components/CardList.tsx';
import { HighlightCard } from '@/components/cards/HighlightCard';
import { MetadataRow } from '@/components/cards/MetadataRow.tsx';
import { useNoteCountsByHighlight } from '@/pages/BookPage/Notes/hooks/useNoteCountsByHighlight.ts';
import { formatDate, formatDuration, formatTime } from '@/utils/date';
import { Box, Typography } from '@mui/material';

interface SessionMetadataProps {
  startTime: string;
  endTime: string;
  startPage: number | null | undefined;
  endPage: number | null | undefined;
}

const SessionMetadata = ({ startTime, endTime, startPage, endPage }: SessionMetadataProps) => {
  const pagesRead = startPage != null && endPage != null ? endPage - startPage : 0;

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 1.5,
        mb: 1.5,
      }}
    >
      <MetadataRow
        items={[
          formatDate(startTime),
          formatTime(startTime),
          formatDuration(startTime, endTime),
          startPage != null && endPage != null && (
            <>
              Pages {startPage}-{endPage}
              {pagesRead > 0 && ` (${pagesRead} page${pagesRead !== 1 ? 's' : ''})`}
            </>
          ),
        ]}
      />
    </Box>
  );
};

interface ReadingSessionCardProps {
  session: ReadingSession;
  bookmarksByHighlightId: Record<number, Bookmark>;
  onOpenHighlight: (sessionId: number, highlightId: number) => void;
}

export const ReadingSessionCard = ({
  session,
  bookmarksByHighlightId,
  onOpenHighlight,
}: ReadingSessionCardProps) => {
  const noteCountByHighlightId = useNoteCountsByHighlight();

  const handleHighlightClick = (highlightId: number) => {
    onOpenHighlight(session.id, highlightId);
  };

  const hasHighlights = session.highlights.length > 0;

  return (
    <Box
      sx={{
        py: 2,
        px: 2.5,
        '@media (max-width: 768px)': {
          px: 2,
          py: 2,
        },
      }}
    >
      <SessionMetadata
        startTime={session.start_time}
        endTime={session.end_time}
        startPage={session.start_page}
        endPage={session.end_page}
      />

      {hasHighlights && (
        <Box sx={{ mt: 3 }}>
          <Typography
            variant="subtitle2"
            sx={{
              mb: 1,
              color: 'text.secondary',
              fontWeight: 600,
            }}
          >
            Highlights ({session.highlights.length})
          </Typography>
          <CardList sx={{ gap: 0 }}>
            {session.highlights.map((highlight) => (
              <li key={highlight.id}>
                <HighlightCard
                  highlight={highlight}
                  bookmark={bookmarksByHighlightId[highlight.id]}
                  noteCount={noteCountByHighlightId[highlight.id]}
                  onOpenModal={handleHighlightClick}
                />
              </li>
            ))}
          </CardList>
        </Box>
      )}
    </Box>
  );
};
