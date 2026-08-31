import { useGetBookStatistics } from '@/api/generated/statistics/statistics';
import { countLabel } from '@/utils/counts.ts';
import { browserTimeZone, formatDate, formatSeconds } from '@/utils/date.ts';
import { Box, LinearProgress, Typography } from '@mui/material';

interface ReadingStatsSectionProps {
  bookId: number;
}

interface StatProps {
  value: string;
  label: string;
}

interface ReadingProgressProps {
  percent: number;
}

interface StatsGridProps {
  stats: StatProps[];
}

/**
 * One number and what it counts. A paragraph rather than a heading: these are
 * facts about the book's reading, not sections of their own.
 */
const Stat = ({ value, label }: StatProps) => (
  <Box>
    <Typography variant="h3" component="p">
      {value}
    </Typography>
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      {label}
    </Typography>
  </Box>
);

const ReadingProgress = ({ percent }: ReadingProgressProps) => (
  <Box sx={{ mb: 3 }}>
    <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
      <Typography variant="h1" component="p">
        {percent}%
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        through the book
      </Typography>
    </Box>
    <LinearProgress
      variant="determinate"
      value={percent}
      aria-label="Reading progress"
      sx={{ mt: 1, height: 8, borderRadius: 1 }}
    />
  </Box>
);

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

export const ReadingStatsSection = ({ bookId }: ReadingStatsSectionProps) => {
  const { data } = useGetBookStatistics(bookId, { tz: browserTimeZone() });

  if (!data || data.session_count === 0) {
    return null;
  }

  const progress = data.progress_percent;

  const stats: StatProps[] = [
    { value: formatSeconds(data.total_reading_seconds), label: 'Time read' },
    { value: String(data.session_count), label: 'Sessions' },
    ...(data.average_session_seconds != null
      ? [{ value: formatSeconds(data.average_session_seconds), label: 'Average session' }]
      : []),
    ...(data.span_days != null
      ? [{ value: countLabel(data.span_days, 'day'), label: 'Reading span' }]
      : []),
    ...(data.last_session_end != null
      ? [{ value: formatDate(data.last_session_end), label: 'Last read' }]
      : []),
  ];

  return (
    <Box sx={{ mb: 4 }}>
      {progress != null && <ReadingProgress percent={progress} />}
      <StatsGrid stats={stats} />
    </Box>
  );
};
