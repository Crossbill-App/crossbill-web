import type { LibraryActivity } from '@/api/generated/model';
import { useGetLibraryReadingActivity } from '@/api/generated/statistics/statistics';
import { Spinner } from '@/components/animations/Spinner.tsx';
import { ReadingActivityGrid } from '@/components/reading/ReadingActivityGrid.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { browserTimeZone } from '@/utils/date.ts';
import { Alert, Box } from '@mui/material';
import { useMemo } from 'react';

/**
 * Books a day is named by before the rest are counted instead. Three fits the
 * width of a tooltip; a day spent grazing over eight books would otherwise
 * make a paragraph of it.
 */
const NAMED_PER_DAY = 3;

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
  const read = useMemo(() => booksByDay(activity), [activity]);

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

      {activity && <ReadingActivityGrid activity={activity} dayNote={(date) => read.get(date)} />}
    </Box>
  );
};
