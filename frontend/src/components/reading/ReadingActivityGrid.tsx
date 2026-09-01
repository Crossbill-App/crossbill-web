import type { BookActivityUnit } from '@/api/generated/model';
import { countLabel } from '@/utils/counts.ts';
import { browserLocale, formatDate } from '@/utils/date.ts';
import { Box, Typography, useTheme } from '@mui/material';
import { DateTime, Info } from 'luxon';
import { cloneElement, useEffect, useMemo, useRef } from 'react';
// The library ships its tooltip styling as a separate stylesheet and imports
// none of it itself; without this the tooltip is unstyled text over the page.
import { ActivityCalendar, type Activity, type DayIndex } from 'react-activity-calendar';
import 'react-activity-calendar/tooltips.css';

/**
 * What the grid needs of an activity response, and no more.
 *
 * Both the book's grid and the library's satisfy it: the library's days carry
 * the books they were spent on as well, which reach the squares through
 * `dayNote` rather than through a second grid.
 */
export interface ActivityGridData {
  unit: BookActivityUnit;
  range_start: string;
  range_end: string;
  days: { date: string; value: number; level: number }[];
}

interface ReadingActivityGridProps {
  activity: ActivityGridData;
  /** What else there is to say about a day, appended to its label. */
  dayNote?: (isoDate: string) => string | undefined;
  /**
   * How wide one day's square is, in pixels. The default matches the library's
   * own; a page with a year's worth of room to spare passes a larger one.
   */
  blockSize?: number;
}

/** The square size the calendar draws at when a page asks for none. */
const DEFAULT_BLOCK_SIZE = 12;

/** The gap between two squares, as a share of the square itself. */
const MARGIN_RATIO = 1 / 3;

/** The calendar's own horizontally scrolling element, by its BEM class. */
const SCROLL_CONTAINER = 'react-activity-calendar__scroll-container';

/** What one square's number counts, as a noun that can be pluralised. */
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
const withWindowBounds = (activity: ActivityGridData): Activity[] => {
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
 * Month names and the first day of the week, as the reader's own locale has
 * them.
 *
 * `getStartOfWeek` returns 1-7 counted from Monday against the calendar's 0-6
 * counted from Sunday, so it is taken modulo 7. It answers from the locale
 * only where the browser exposes `Intl.Locale`'s week info; Firefox does not,
 * and Luxon falls back to Monday there whatever the locale.
 */
const useCalendarLocale = () =>
  useMemo(() => {
    const locale = browserLocale();

    return {
      locale,
      months: Info.months('short', { locale }),
      weekStart: (Info.getStartOfWeek({ locale }) % 7) as DayIndex,
    };
  }, []);

/**
 * The reading one day got, as a sentence.
 *
 * The same words label the square for a screen reader and fill its tooltip.
 * On a phone the label is the only way to the number at all, since a tooltip
 * needs a pointer to hover -- which is why the books of a day are said here
 * rather than drawn somewhere only a mouse can reach.
 */
const dayLabel = (activity: ActivityGridData, day: Activity, note?: string) => {
  const reading = `${countLabel(day.count, UNIT_NOUN[activity.unit])} on ${formatDate(day.date)}`;
  return note ? `${reading} — ${note}` : reading;
};

/**
 * A year of squares, one per day, darker the more of the book that day got
 * through, scrolling sideways in a column too narrow for it.
 *
 * Carries no outer spacing: the page that shows it -- under a book's numbers,
 * or under a section heading on the dashboard -- owns where it sits.
 *
 * The scrolling is the calendar's own — it ships a scroll container around its
 * SVG — so this box sizes and pads rather than scrolls; a second scroller
 * nested inside the first only clips the right edge.
 *
 * The weekday rail stays off. The calendar draws those labels at negative x
 * inside the SVG and pushes the SVG clear with a left margin, so they ride
 * along with the grid rather than being pinned beside it: scroll right and
 * they slide under the container's edge half a letter at a time.
 */
export const ReadingActivityGrid = ({
  activity,
  dayNote,
  blockSize = DEFAULT_BLOCK_SIZE,
}: ReadingActivityGridProps) => {
  const theme = useTheme();
  const { locale, months, weekStart } = useCalendarLocale();
  const data = useMemo(() => withWindowBounds(activity), [activity]);
  const section = useRef<HTMLDivElement>(null);

  // Opened on the most recent weeks, which is what a reader came to see. The
  // calendar's own scroll container is the one to move, and it is reached by
  // its class because the component forwards a ref to its outer element only.
  // The frame is waited out because the grid is still being laid out on the
  // first pass.
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const scroller = section.current?.querySelector(`.${SCROLL_CONTAINER}`);
      if (scroller) {
        scroller.scrollLeft = scroller.scrollWidth;
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [data]);

  const asMonth = (date: string) =>
    DateTime.fromISO(date).setLocale(locale).toLocaleString({ month: 'short', year: 'numeric' });

  return (
    <Box
      ref={section}
      sx={{
        // `minWidth: 0` so the calendar's own `max-width: 100%` has a real
        // width to measure against: a flex or grid child sized `auto` refuses
        // to shrink, and the grid would widen the page instead of scrolling.
        minWidth: 0,
        // The squares carry a 1px stroke that paints half a pixel past the
        // SVG's declared width, and the scroll container's overflow clips it.
        [`& .${SCROLL_CONTAINER}`]: { paddingRight: '2px', paddingBottom: 1 },
      }}
    >
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1.5 }}>
        {asMonth(activity.range_start)} – {asMonth(activity.range_end)} · {activity.unit} read
      </Typography>

      <ActivityCalendar
        data={data}
        // The app has one colour scheme; left to itself the calendar would read
        // the reader's OS setting and swap in its own grey dark ramp.
        colorScheme="light"
        theme={{
          light: [theme.customColors.activityGrid.empty, theme.customColors.activityGrid.full],
        }}
        blockSize={blockSize}
        blockMargin={Math.round(blockSize * MARGIN_RATIO)}
        showTotalCount={false}
        labels={{ months, legend: { less: 'Less', more: 'More' } }}
        renderBlock={(block, day) =>
          cloneElement(block, {
            role: 'img',
            'aria-label': dayLabel(activity, day, dayNote?.(day.date)),
          })
        }
        tooltips={{ activity: { text: (day) => dayLabel(activity, day, dayNote?.(day.date)) } }}
        weekStart={weekStart}
      />
    </Box>
  );
};
