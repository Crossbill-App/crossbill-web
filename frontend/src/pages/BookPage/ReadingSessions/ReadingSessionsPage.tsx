import type { ReadingSession } from '@/api/generated/model';
import { useGetBookReadingSessions } from '@/api/generated/reading-sessions/reading-sessions';
import { useGetTags } from '@/api/generated/tags/tags';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { HighlightViewModal } from '@/pages/BookPage/Highlights/HighlightViewModal/HighlightViewModal';
import { useHighlightModal } from '@/pages/BookPage/Highlights/hooks/useHighlightModal';
import { Alert, Box, Pagination } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { keyBy } from 'lodash';
import { useMemo, useState } from 'react';
import { ReadingSessionList } from './ReadingSessionList';

const SESSIONS_PER_PAGE = 30;

export const ReadingSessionsPage = () => {
  const { book, isDesktop } = useBookPage();

  const { sessionPage } = useSearch({ from: '/book/$bookId/sessions' });
  const navigate = useNavigate({ from: '/book/$bookId/sessions' });

  const currentPage = sessionPage || 1;
  const offset = (currentPage - 1) * SESSIONS_PER_PAGE;

  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);

  const bookmarksByHighlightId = useMemo(
    () => keyBy(book.bookmarks, 'highlight_id'),
    [book.bookmarks]
  );

  const { data: tagsResponse } = useGetTags(book.id);

  const { data, isLoading, isError } = useGetBookReadingSessions(book.id, {
    limit: SESSIONS_PER_PAGE,
    offset,
  });

  const activeSession = useMemo(
    () => data?.items.find((s: ReadingSession) => s.id === activeSessionId) || null,
    [data?.items, activeSessionId]
  );

  const sessionHighlights = useMemo(() => activeSession?.highlights || [], [activeSession]);

  const {
    openHighlightId,
    currentHighlight,
    currentHighlightIndex,
    handleOpenHighlight,
    handleCloseHighlight,
    handleModalNavigate,
  } = useHighlightModal({
    allHighlights: sessionHighlights,
    isMobile: !isDesktop,
    syncToUrl: false,
  });

  const handleOpenSessionHighlight = (sessionId: number, highlightId: number) => {
    setActiveSessionId(sessionId);
    handleOpenHighlight(highlightId);
  };

  const handleCloseModal = (lastViewedHighlightId?: number) => {
    handleCloseHighlight(lastViewedHighlightId);
    setActiveSessionId(null);
  };

  const handlePageChange = (_event: React.ChangeEvent<unknown>, value: number) => {
    navigate({
      search: (prev) => ({
        ...prev,
        sessionPage: value === 1 ? undefined : value,
      }),
      replace: true,
    });
  };

  const totalPages = data?.total ? Math.ceil(data.total / SESSIONS_PER_PAGE) : 0;

  return (
    <>
      <Box>
        {isLoading && <Spinner />}

        {isError && (
          <Box sx={{ py: 3 }}>
            <Alert severity="error">Failed to load reading sessions. Please try again later.</Alert>
          </Box>
        )}

        {data && (
          <>
            <ReadingSessionList
              sessions={data.items}
              animationKey={`reading-sessions-${currentPage}`}
              bookmarksByHighlightId={bookmarksByHighlightId}
              onOpenHighlight={handleOpenSessionHighlight}
            />
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <Pagination
                  count={totalPages}
                  page={currentPage}
                  onChange={handlePageChange}
                  color="primary"
                  size="large"
                  showFirstButton
                  showLastButton
                />
              </Box>
            )}
          </>
        )}
      </Box>

      {currentHighlight && (
        <HighlightViewModal
          highlight={currentHighlight}
          bookId={book.id}
          open={!!openHighlightId}
          onClose={handleCloseModal}
          availableTags={tagsResponse?.items || []}
          bookmarksByHighlightId={bookmarksByHighlightId}
          allHighlights={sessionHighlights}
          currentIndex={currentHighlightIndex}
          onNavigate={handleModalNavigate}
        />
      )}
    </>
  );
};
