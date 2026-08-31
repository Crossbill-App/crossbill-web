import type { BookActivity } from '@/api/generated/model';
import { useGetBookStatistics } from '@/api/generated/statistics/statistics';
import { EmptyStateText } from '@/components/EmptyStateText.tsx';
import { SectionTitle } from '@/components/typography/SectionTitle.tsx';
import { countLabel } from '@/utils/counts.ts';
import { browserLocale, browserTimeZone, formatDate } from '@/utils/date.ts';
import { Box, Typography, useTheme } from '@mui/material';
import { DateTime, Info } from 'luxon';
import { useEffect, useMemo, useRef } from 'react';
// The library ships its tooltip styling as a separate stylesheet and imports
// none of it itself; without this the tooltip is unstyled text over the page.
// Its dark bubble is the shape MUI's own tooltips take, so it reads as part of
// the app rather than beside it.
import { ActivityCalendar, type Activity, type DayIndex } from 'react-activity-calendar';
import 'react-activity-calendar/tooltips.css';

interface ReadingActivitySectionProps {
  bookId: number;
}

interface ActivityGridProps {
  activity: BookActivity;
}

/** What one square's number counts, as a noun a tooltip can pluralise. */
const UNIT_NOUN = { pages: 'page', minutes: 'minute' } as const;

/**
 * The grid's own data, spanning the whole window rather than only the days
 * that were read.
 *
 * The backend sends the days with something to show and the window separately,
 * because a year of mostly-zero entries is ten times the payload for the same
 * picture. The library derives the grid's extent from its first and last entry
 * and fills every gap between them itself, so the two bounds are all it needs
 * back.
 */
const withWindowBounds = (activity: BookActivity): Activity[] => {
  const byDate = new Map<string, Activity>(
    activity.days.map((day) => [day.date, { date: day.date, count: day.value, level: day.level }])
  );

  for (const date of [activity.range_start, activity.range_end]) {
    if (!byDate.has(date)) {
      byDate.set(date, { date, count: 0, level: 0 });
    }
  }

  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
};

/**
 * Month names, weekday names and the first day of the week, as the reader's
 * own locale has them.
 *
 * Luxon counts weekdays from Monday and the calendar indexes them from Sunday,
 * so the list is rotated rather than passed straight through; `getStartOfWeek`
 * likewise returns 1-7 from Monday against the calendar's 0-6 from Sunday.
 */
const useCalendarLocale = () =>
  useMemo(() => {
    const locale = browserLocale();
    const fromMonday = Info.weekdays('short', { locale });

    return {
      locale,
      months: Info.months('short', { locale }),
      weekdays: [fromMonday[6], ...fromMonday.slice(0, 6)],
      weekStart: (Info.getStartOfWeek({ locale }) % 7) as DayIndex,
    };
  }, []);

/** "Sep 2025 – Aug 2026 · pages read" — the window the grid covers, and its unit. */
const RangeCaption = ({ activity }: ActivityGridProps) => {
  const { locale } = useCalendarLocale();
  const asMonth = (date: string) =>
    DateTime.fromISO(date).setLocale(locale).toLocaleString({ month: 'short', year: 'numeric' });

  return (
    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
      {asMonth(activity.range_start)} – {asMonth(activity.range_end)} · {activity.unit} read
    </Typography>
  );
};

/**
 * A year of squares, at one fixed size, scrolled sideways when the column is
 * too narrow for it.
 *
 * Shrinking the squares to fit instead was the other option, and it does not
 * work: a month label is as wide as its longest name, not as wide as the four
 * or five columns beneath it, so at phone widths the months collide into an
 * unreadable row. The squares also fall well under the app's 48px touch
 * minimum long before a year fits. At a fixed size the grid stays legible and
 * tappable, and the overflow is contained here rather than left to nudge the
 * whole page sideways.
 */
const ActivityGrid = ({ activity }: ActivityGridProps) => {
  const theme = useTheme();
  const { months, weekdays, weekStart } = useCalendarLocale();
  const data = useMemo(() => withWindowBounds(activity), [activity]);
  const noun = UNIT_NOUN[activity.unit];
  const scroller = useRef<HTMLDivElement>(null);

  // Opened on the most recent weeks, which is what a reader came to see. The
  // frame is waited out because the calendar measures its weekday rail in an
  // effect of its own, so the grid is still growing on the first pass.
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const element = scroller.current;
      if (element) {
        element.scrollLeft = element.scrollWidth;
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [data]);

  return (
    // `minWidth: 0` so the box may actually be narrower than the grid inside
    // it: a flex or grid child sized `auto` refuses to, and the overflow would
    // widen the page instead of scrolling here.
    <Box ref={scroller} sx={{ overflowX: 'auto', maxWidth: '100%', minWidth: 0, pb: 1 }}>
      <ActivityCalendar
        data={data}
        // The app has one colour scheme; left to itself the calendar would read
        // the reader's OS setting and swap in its own grey dark ramp.
        colorScheme="light"
        theme={{
          light: [theme.customColors.activityGrid.empty, theme.customColors.activityGrid.full],
        }}
        showWeekdayLabels
        showTotalCount={false}
        labels={{
          months,
          weekdays,
          legend: { less: 'Less', more: 'More' },
        }}
        tooltips={{
          activity: {
            text: (day) => `${countLabel(day.count, noun)} on ${formatDate(day.date)}`,
          },
        }}
        weekStart={weekStart}
      />
    </Box>
  );
};

/**
 * The reading-activity grid: a year of squares, one per day, darker the more
 * of the book that day got through.
 *
 * Reads the same statistics query as the summary above it, so the grid costs
 * no second request. While that query is loading or failing there is nothing
 * to say here — the summary raises the failure — so the section renders only
 * once an answer has arrived.
 */
export const ReadingActivitySection = ({ bookId }: ReadingActivitySectionProps) => {
  const { data } = useGetBookStatistics(bookId, { tz: browserTimeZone() });

  if (!data) {
    return null;
  }

  return (
    <Box sx={{ mb: 4 }}>
      <SectionTitle showDivider>Reading activity</SectionTitle>

      {data.activity ? (
        <>
          <RangeCaption activity={data.activity} />
          <ActivityGrid activity={data.activity} />
        </>
      ) : (
        <EmptyStateText>No reading activity recorded yet.</EmptyStateText>
      )}
    </Box>
  );
};
