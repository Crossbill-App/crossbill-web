import type { Bookmark, ReadingSession } from '@/api/generated/model';
import { FadeInOut } from '@/components/animations/FadeInOut';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
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
        <CardList sx={{ gap: 0 }} aria-label="Reading sessions">
          {sessions.map((session) => (
            <li key={session.id}>
              <ReadingSessionCard
                session={session}
                bookmarksByHighlightId={bookmarksByHighlightId}
                onOpenHighlight={onOpenHighlight}
              />
            </li>
          ))}
        </CardList>
      )}
    </FadeInOut>
  );
};
