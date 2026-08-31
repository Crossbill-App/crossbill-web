import { ReadingStatisticsPage } from '@/pages/BookPage/ReadingStatistics/ReadingStatisticsPage';
import { createFileRoute } from '@tanstack/react-router';

type StatisticsSearch = {
  sessionPage?: number;
};

export const Route = createFileRoute('/book/$bookId/statistics')({
  component: ReadingStatisticsPage,
  validateSearch: (search: Record<string, unknown>): StatisticsSearch => ({
    sessionPage: search.sessionPage ? Number(search.sessionPage) : undefined,
  }),
});
