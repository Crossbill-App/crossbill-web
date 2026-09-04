import type { LibraryActivity, LibraryStats } from '@/api/generated/model';
import { useGetLibraryReadingActivity } from '@/api/generated/statistics/statistics';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { ReadingActivityGrid } from '@/components/reading/ReadingActivityGrid.tsx';
import { Stat, type StatProps } from '@/components/reading/Stat.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { countLabel } from '@/utils/counts.ts';
import { browserTimeZone, formatDay, formatSeconds } from '@/utils/date.ts';
import { Alert, Box, useMediaQuery } from '@mui/material';
import { useMemo } from 'react';
import { RECENT_ROW_WIDTH } from './RecentBooks.tsx';

/** Books a day is named by before the rest are counted instead. */
const NAMED_PER_DAY = 3;

/**
 * The narrowest the numbers may be squeezed to. Any wider and the floor, the
 * gap and a year of default squares outgrow the content column at `lg`.
 */
const STATS_COLUMN = 260;

const STATS_GAP = 32;

const ROOMY_BLOCK_SIZE = 15;

/** A media query counts the scrollbar in, leaving some 15px less to lay out in. */
const ROOMY_SLACK = 40;

/**
 * The narrowest viewport that fits a whole year of `ROOMY_BLOCK_SIZE` squares
 * beside the numbers: 53 columns of a square plus its third of a gap, then the
 * stats column, the gap and the page's own 48px of gutter.
 */
const ROOMY_VIEWPORT = 53 * (ROOMY_BLOCK_SIZE + 5) + STATS_COLUMN + STATS_GAP + 48 + ROOMY_SLACK;

/** The books of one day, as the reader would say them. */
const booksLabel = (titles: string[]) => {
  if (titles.length <= NAMED_PER_DAY) {
    return titles.join(', ');
  }
  const rest = titles.length - NAMED_PER_DAY;
  return `${titles.slice(0, NAMED_PER_DAY).join(', ')} and ${rest} more`;
};

/**
 * What was read on each day. The response names each book once and references
 * it by id, so the titles are joined back up here.
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
 * The dashboard's year of reading. A reader with nothing on the grid still gets
 * the grid, empty, with a line saying what will colour it: a blank year reads
 * as a year yet to be filled, where a missing section reads as a missing page.
 * The numbers wait until there is something to count.
 */
export const ReadingActivity = () => {
  const { data, isLoading, isError } = useGetLibraryReadingActivity({ tz: browserTimeZone() });
  const activity = data?.activity;
  const stats = data?.stats;
  const read = useMemo(() => booksByDay(activity), [activity]);
  const roomy = useMediaQuery(`(min-width: ${ROOMY_VIEWPORT}px)`);

  const empty = !isLoading && !isError && !activity;

  return (
    <Box sx={{ mb: 6 }}>
      <SectionTitle showDivider>Reading activity</SectionTitle>

      {isLoading && <Spinner />}

      {isError && (
        <Box sx={{ py: 3 }}>
          <Alert severity="error">Failed to load reading activity.</Alert>
        </Box>
      )}

      {empty && (
        <>
          <EmptyStateText>
            No reading recorded yet. Your reading days fill in here once you sync your e-reader.
          </EmptyStateText>

          <Box sx={{ mt: 3, maxWidth: { lg: `${RECENT_ROW_WIDTH}px` } }}>
            <ReadingActivityGrid activity={null} blockSize={roomy ? ROOMY_BLOCK_SIZE : undefined} />
          </Box>
        </>
      )}

      {activity && (
        <Box
          sx={{
            display: 'grid',
            // The numbers read first on a phone, where the grid has to be
            // scrolled to be read at all.
            gridTemplateAreas: { xs: '"stats" "grid"', lg: '"stats grid"' },
            // The grid takes the width a year needs and the numbers take what
            // is left: it is the grid's right edge that has to meet the covers.
            gridTemplateColumns: { xs: '1fr', lg: `minmax(${STATS_COLUMN}px, 1fr) auto` },
            maxWidth: { lg: `${RECENT_ROW_WIDTH}px` },
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
                // So the two columns read as one band.
                alignContent: 'center',
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
