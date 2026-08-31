import { useGetBookReadingSessions } from '@/api/generated/reading-sessions/reading-sessions';
import { FadeInOut } from '@/components/animations/FadeInOut';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { PaginationControls } from '@/components/PaginationControls.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { PageHeader } from '@/pages/BookPage/common/PageHeader.tsx';
import { BOOK_PAGE_LABELS } from '@/pages/BookPage/navigation/bookPageRoutes.ts';
import { Alert, Box } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { ReadingStatsSection } from './ReadingStatsSection.tsx';
import { SessionCard } from './SessionCard';

const SESSIONS_PER_PAGE = 5;

export const ReadingStatisticsPage = () => {
  const { book } = useBookPage();

  const { sessionPage } = useSearch({ from: '/book/$bookId/statistics' });
  const navigate = useNavigate({ from: '/book/$bookId/statistics' });

  const currentPage = sessionPage || 1;
  const offset = (currentPage - 1) * SESSIONS_PER_PAGE;

  const { data, isLoading, isError } = useGetBookReadingSessions(book.id, {
    limit: SESSIONS_PER_PAGE,
    offset,
  });

  const handlePageChange = (value: number) => {
    void navigate({
      search: (prev) => ({
        ...prev,
        sessionPage: value === 1 ? undefined : value,
      }),
      replace: true,
    });
  };

  const totalPages = data?.total ? Math.ceil(data.total / SESSIONS_PER_PAGE) : 0;

  return (
    <Box>
      <PageHeader title={BOOK_PAGE_LABELS.statistics} />

      <ReadingStatsSection bookId={book.id} />

      <SectionTitle showDivider>Sessions</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load reading sessions. Please try again later.</Alert>
        </Box>
      )}

      {data && (
        // Paging refetches, and the page unmounts this list while it loads, so
        // `animateOnMount={false}` would suppress the very fade it is meant to
        // preserve.
        <FadeInOut ekey={`reading-sessions-${currentPage}`}>
          {data.items.length === 0 ? (
            <EmptyStateText variant="page">No reading sessions recorded yet.</EmptyStateText>
          ) : (
            <CardList aria-label="Reading sessions">
              {data.items.map((session) => (
                <li key={session.id}>
                  <SessionCard session={session} />
                </li>
              ))}
            </CardList>
          )}

          <PaginationControls count={totalPages} page={currentPage} onChange={handlePageChange} />
        </FadeInOut>
      )}
    </Box>
  );
};
