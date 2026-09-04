import type { BookActivityUnit } from '@/api/generated/model';
import { countLabel } from '@/utils/counts.ts';
import { browserLocale, formatDate } from '@/utils/date.ts';
import { Box, useTheme } from '@mui/material';
import { DateTime, Info } from 'luxon';
import { cloneElement, useEffect, useMemo, useRef } from 'react';
import { ActivityCalendar, type Activity, type DayIndex } from 'react-activity-calendar';
// Shipped separately; the library imports none of it itself.
import 'react-activity-calendar/tooltips.css';

/** What the grid needs of an activity response, and no more. */
export interface ActivityGridData {
  unit: BookActivityUnit;
  range_start: string;
  range_end: string;
  days: { date: string; value: number; level: number }[];
}

interface ReadingActivityGridProps {
  /**
   * The reading to draw, or `null` for the blank year a reader with nothing
   * read yet is shown -- an empty grid says what no grid at all cannot.
   */
  activity: ActivityGridData | null;
  /** What else there is to say about a day, appended to its label. */
  dayNote?: (isoDate: string) => string | undefined;
  blockSize?: number;
}

/** The window a grid spans, and whichever of its days are worth colouring. */
type ActivityWindow = Pick<ActivityGridData, 'range_start' | 'range_end' | 'days'>;

const DEFAULT_BLOCK_SIZE = 12;

/** Days a grid spans, the last one included -- the window the backend draws. */
const WINDOW_DAYS = 365;

/** The gap between two squares, as a share of the square itself. */
const MARGIN_RATIO = 1 / 3;

const SCROLL_CONTAINER = 'react-activity-calendar__scroll-container';

/** The footer slot the calendar keeps for a total. */
const FOOTER_CAPTION = 'react-activity-calendar__count';

const UNIT_NOUN = { pages: 'page', minutes: 'minute' } as const;

/**
 * The backend sends only the days worth drawing, so the window's own bounds go
 * in as empty days; the library fills every gap between its first and last.
 */
const withWindowBounds = (activity: ActivityWindow): Activity[] => {
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

/** The year ending today, with no day coloured on it. */
const emptyYear = (): ActivityWindow => ({
  range_start: DateTime.now()
    .minus({ days: WINDOW_DAYS - 1 })
    .toFormat('yyyy-MM-dd'),
  range_end: DateTime.now().toFormat('yyyy-MM-dd'),
  days: [],
});

/**
 * `getStartOfWeek` counts 1-7 from Monday against the calendar's 0-6 from
 * Sunday, hence the modulo. Firefox exposes no week info and always says Monday.
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
 * Labels the square and fills its tooltip both, since a phone has no pointer to
 * hover with and the label is its only way to the number.
 */
const dayLabel = (activity: ActivityGridData | null, day: Activity, note?: string) => {
  if (!activity) {
    return `Nothing read on ${formatDate(day.date)}`;
  }

  const reading = `${countLabel(day.count, UNIT_NOUN[activity.unit])} on ${formatDate(day.date)}`;
  return note ? `${reading} — ${note}` : reading;
};

/**
 * A year of squares, one per day, darker the more of the book that day got
 * through, scrolling sideways in a column too narrow for it.
 *
 * The scrolling is the calendar's own, so this box sizes and pads rather than
 * scrolls. The weekday rail stays off: those labels are drawn at negative x
 * inside the SVG, so they scroll away with it rather than staying pinned.
 */
export const ReadingActivityGrid = ({
  activity,
  dayNote,
  blockSize = DEFAULT_BLOCK_SIZE,
}: ReadingActivityGridProps) => {
  const theme = useTheme();
  const { locale, months, weekStart } = useCalendarLocale();
  // A reader with nothing read still gets a year of squares, all uncoloured.
  const span = useMemo(() => activity ?? emptyYear(), [activity]);
  const data = useMemo(() => withWindowBounds(span), [span]);
  const section = useRef<HTMLDivElement>(null);

  // Opened on the most recent weeks. Reached by class because the component
  // forwards a ref to its outer element only, and a frame late because the
  // grid is still being laid out on the first pass.
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const scroller = section.current?.querySelector(`.${SCROLL_CONTAINER}`);
      if (scroller) {
        scroller.scrollLeft = scroller.scrollWidth;
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [data, blockSize]);

  const asMonth = (date: string) =>
    DateTime.fromISO(date).setLocale(locale).toLocaleString({ month: 'short', year: 'numeric' });

  const period = `${asMonth(span.range_start)} – ${asMonth(span.range_end)}`;

  return (
    <Box
      ref={section}
      sx={{
        // So the calendar's `max-width: 100%` has a real width to measure
        // against; a grid child sized `auto` refuses to shrink.
        minWidth: 0,
        // The squares' 1px stroke paints half a pixel past the SVG's width,
        // which the scroll container would otherwise clip.
        [`& .${SCROLL_CONTAINER}`]: { paddingRight: '2px', paddingBottom: 1 },
        [`& .${FOOTER_CAPTION}`]: { color: 'text.secondary' },
      }}
    >
      <ActivityCalendar
        data={data}
        // The app has one colour scheme; the calendar would otherwise follow
        // the reader's OS setting into its own grey dark ramp.
        colorScheme="light"
        theme={{
          light: [theme.customColors.activityGrid.empty, theme.customColors.activityGrid.full],
        }}
        blockSize={blockSize}
        blockMargin={Math.round(blockSize * MARGIN_RATIO)}
        // A scale from less to more explains nothing on a grid with neither.
        showColorLegend={activity !== null}
        labels={{
          months,
          legend: { less: 'Less', more: 'More' },
          totalCount: activity
            ? `${period} · ${activity.unit} read`
            : `${period} · nothing read yet`,
        }}
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
