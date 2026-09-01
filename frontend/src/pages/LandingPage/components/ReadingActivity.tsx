import type { LibraryActivity, LibraryStats } from '@/api/generated/model';
import { useGetLibraryReadingActivity } from '@/api/generated/statistics/statistics';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { ReadingActivityGrid } from '@/components/reading/ReadingActivityGrid.tsx';
import { Stat, type StatProps } from '@/components/reading/Stat.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { countLabel } from '@/utils/counts.ts';
import { browserTimeZone, formatDay, formatSeconds } from '@/utils/date.ts';
import { Alert, Box, useMediaQuery } from '@mui/material';
import { useMemo } from 'react';

/**
 * Books a day is named by before the rest are counted instead. Three fits the
 * width of a tooltip; a day spent grazing over eight books would otherwise
 * make a paragraph of it.
 */
const NAMED_PER_DAY = 3;

/** How wide the column of numbers is, where it sits beside the grid. */
const STATS_COLUMN = 280;

/** The gap between that column and the grid, in pixels. */
const STATS_GAP = 32;

/** The square size the grid is drawn at once the row is wide enough for it. */
const ROOMY_BLOCK_SIZE = 15;

/**
 * The narrowest viewport that fits a whole year of `ROOMY_BLOCK_SIZE` squares
 * beside the numbers: 53 columns of a square plus its third of a gap, then the
 * stats column, the gap and the page's own 48px of gutter. Below it the grid
 * keeps the size the book page draws it at rather than scrolling wider squares.
 */
const ROOMY_VIEWPORT = 53 * (ROOMY_BLOCK_SIZE + 5) + STATS_COLUMN + STATS_GAP + 48;

/** The books of one day, as the reader would say them. */
const booksLabel = (titles: string[]) => {
  if (titles.length <= NAMED_PER_DAY) {
    return titles.join(', ');
  }
  const rest = titles.length - NAMED_PER_DAY;
  return `${titles.slice(0, NAMED_PER_DAY).join(', ')} and ${rest} more`;
};

/**
 * What was read on each day, by date.
 *
 * The response names each book once and references it by id from every day it
 * appears on, so the titles are joined back up here. An id with no title is
 * skipped rather than shown as a gap.
 */
const booksByDay = (activity: LibraryActivity | null | undefined): Map<string, string> => {
  const titles = new Map((activity?.books ?? []).map((book) => [book.id, book.title]));

  return new Map(
    (activity?.days ?? []).map((day) => [
      day.date,
      booksLabel(day.book_ids.map((id) => titles.get(id)).filter((title) => title !== undefined)),
    ])
  );
};

/** The year said in numbers, in the order a reader would ask for them. */
const summary = (stats: LibraryStats): StatProps[] => [
  { value: formatSeconds(stats.seconds_today), label: 'Time read today' },
  { value: formatDay(stats.last_read), label: 'Last read' },
  { value: countLabel(stats.streak_days, 'day'), label: 'Current streak' },
  { value: String(stats.days_read), label: 'Days read' },
  { value: String(stats.books_read), label: 'Books read' },
  { value: formatSeconds(stats.total_seconds), label: 'Total time read' },
];

/**
 * The dashboard's year of reading: one square per day across the whole library,
 * darker the more of it that day got through, and the books each day was spent
 * on in the square's own label.
 *
 * The section is not drawn at all for a reader with nothing on the grid — a
 * blank year is worse than no year, and a new reader would meet it first.
 */
export const ReadingActivity = () => {
  const { data, isLoading, isError } = useGetLibraryReadingActivity({ tz: browserTimeZone() });
  const activity = data?.activity;
  const stats = data?.stats;
  const read = useMemo(() => booksByDay(activity), [activity]);
  const roomy = useMediaQuery(`(min-width: ${ROOMY_VIEWPORT}px)`);

  if (!isLoading && !isError && !activity) {
    return null;
  }

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Reading activity</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load reading activity.</Alert>
        </Box>
      )}

      {activity && (
        <Box
          sx={{
            display: 'grid',
            // The numbers read first on a phone, where they sit above a grid
            // that has to be scrolled to be read at all; on a desktop they
            // take the empty half of the row beside it.
            gridTemplateAreas: { xs: '"stats" "grid"', lg: '"grid stats"' },
            gridTemplateColumns: { xs: '1fr', lg: `minmax(0, 1fr) ${STATS_COLUMN}px` },
            columnGap: `${STATS_GAP}px`,
            rowGap: 3,
          }}
        >
          <Box sx={{ gridArea: 'grid', minWidth: 0 }}>
            <ReadingActivityGrid
              activity={activity}
              dayNote={(date) => read.get(date)}
              blockSize={roomy ? ROOMY_BLOCK_SIZE : undefined}
            />
          </Box>

          {stats && (
            <Box
              sx={{
                gridArea: 'stats',
                display: 'grid',
                gridTemplateColumns: {
                  xs: 'repeat(2, 1fr)',
                  sm: 'repeat(3, 1fr)',
                  lg: 'repeat(2, 1fr)',
                },
                gap: 2,
                alignContent: 'start',
              }}
            >
              {summary(stats).map((stat) => (
                <Stat key={stat.label} value={stat.value} label={stat.label} />
              ))}
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};
