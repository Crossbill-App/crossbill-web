import { useGetBookStatistics } from '@/api/generated/statistics/statistics';
import { ReadingActivityGrid } from '@/components/reading/ReadingActivityGrid.tsx';
import { Stat, type StatProps } from '@/components/reading/Stat.tsx';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { browserTimeZone, formatDate, formatSeconds } from '@/utils/date.ts';
import { Box, LinearProgress, Typography } from '@mui/material';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

interface ReadingStatsSectionProps {
  bookId: number;
}

interface ReadingProgressProps {
  percent: number;
}

interface StatsGridProps {
  stats: StatProps[];
}

const ReadingProgress = ({ percent }: ReadingProgressProps) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
        <Typography variant="h1" component="p">
          {t('book.statistics.progress.percent', { percent })}
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {t('book.statistics.progress.throughTheBook')}
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={percent}
        aria-label={t('book.statistics.progress.ariaLabel')}
        sx={{ mt: 1, height: 8, borderRadius: 1 }}
      />
    </Box>
  );
};

const StatsGrid = ({ stats }: StatsGridProps) => (
  <Box
    sx={{
      display: 'grid',
      gridTemplateColumns: {
        xs: 'repeat(2, 1fr)',
        sm: 'repeat(3, 1fr)',
        md: `repeat(${stats.length}, 1fr)`,
      },
      gap: 2,
    }}
  >
    {stats.map((stat) => (
      <Stat key={stat.label} value={stat.value} label={stat.label} />
    ))}
  </Box>
);

/**
 * What a book's reading adds up to: how far through it the reader is, the
 * numbers, and the year of squares. Drawn for a book nobody has opened too,
 * with zeroes and an empty grid -- the sessions list below says the same in
 * words, and a summary that disappears reads as a page that failed to load.
 */
export const ReadingStatsSection = ({ bookId }: ReadingStatsSectionProps) => {
  const { data, isError } = useGetBookStatistics(bookId, { tz: browserTimeZone() });
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();

  // The summary is the smaller half of the tab, so a failure is reported
  // beside the sessions rather than in place of them.
  useEffect(() => {
    if (isError) {
      showSnackbar(t('book.statistics.loadError'), 'error');
    }
  }, [isError, showSnackbar, t]);

  if (!data) {
    return null;
  }

  // A book with no session behind it is at the start of it rather than at an
  // unknown place, so the bar reads 0% instead of going missing.
  const progress = data.progress_percent ?? (data.session_count === 0 ? 0 : null);

  const stats: StatProps[] = [
    {
      value: formatSeconds(data.total_reading_seconds),
      label: t('book.statistics.stats.timeRead'),
    },
    { value: String(data.session_count), label: t('common.entities.sessions') },
    ...(data.average_session_seconds != null
      ? [
          {
            value: formatSeconds(data.average_session_seconds),
            label: t('book.statistics.stats.averageSession'),
          },
        ]
      : []),
    ...(data.span_days != null
      ? [
          {
            value: t('common.counts.days', { count: data.span_days }),
            label: t('book.statistics.stats.readingSpan'),
          },
        ]
      : []),
    ...(data.last_session_end != null
      ? [{ value: formatDate(data.last_session_end), label: t('common.labels.lastRead') }]
      : []),
  ];

  return (
    <Box sx={{ mb: 4 }}>
      {progress != null && <ReadingProgress percent={progress} />}
      <StatsGrid stats={stats} />
      {/* The grid is more of the same summary, not a section of its own, so it
          sits under the numbers rather than beside them with a heading. A book
          with nothing read yet gets the year empty rather than not at all. */}
      <Box sx={{ mt: 4 }}>
        <ReadingActivityGrid activity={data.activity ?? null} />
      </Box>
    </Box>
  );
};
