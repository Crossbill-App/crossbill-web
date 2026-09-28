import { useGetBookReadingSessions } from '@/api/generated/reading-sessions/reading-sessions';
import { FadeInOut } from '@/components/animations/FadeInOut';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { CardList } from '@/components/CardList.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { PageHeader } from '@/components/layout/PageHeader.tsx';
import { PaginationControls } from '@/components/PaginationControls.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { useBookPage } from '@/pages/BookPage/BookPageContext';
import { BOOK_PAGE_LABEL_KEYS } from '@/pages/BookPage/navigation/bookPageRoutes.ts';
import { Alert, Box } from '@mui/material';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { ReadingStatsSection } from './ReadingStatsSection.tsx';
import { SessionCard } from './SessionCard';

const SESSIONS_PER_PAGE = 5;

export const ReadingStatisticsPage = () => {
  const { t } = useTranslation();
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
      <PageHeader title={t(BOOK_PAGE_LABEL_KEYS.statistics)} />

      <ReadingStatsSection bookId={book.id} />

      <SectionTitle showDivider>{t('common.entities.sessions')}</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">{t('book.statistics.sessions.loadError')}</Alert>
        </Box>
      )}

      {data && (
        // Paging refetches, and the page unmounts this list while it loads, so
        // `animateOnMount={false}` would suppress the very fade it is meant to
        // preserve.
        <FadeInOut ekey={`reading-sessions-${currentPage}`}>
          {data.items.length === 0 ? (
            <EmptyStateText variant="page">{t('book.statistics.sessions.empty')}</EmptyStateText>
          ) : (
            <CardList aria-label={t('book.statistics.sessions.listLabel')}>
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
