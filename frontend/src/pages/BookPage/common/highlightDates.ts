import type { ChapterWithHighlights } from '@/api/generated/model';
import { formatDateTime } from '@/utils/date.ts';
import { DateTime } from 'luxon';

export const DATE_SEARCH_FORMAT = 'yyyy-MM-dd';
const HIGHLIGHT_DATETIME_FORMAT = 'yyyy-MM-dd HH:mm:ss';

export interface HighlightDateRange {
  from?: string;
  to?: string;
}

/**
 * The locale pin is about digits, not date order. These formats are numeric,
 * but luxon parses and re-renders in the ambient locale's numbering system, so
 * for a reader on `ar-EG` the round-trip below comes back in Arabic-Indic
 * digits and rejects a perfectly good timestamp, and on `hi-IN-u-nu-deva` the
 * parse fails outright.
 */
const parseStrictly = (value: string, format: string): DateTime | undefined => {
  const parsed = DateTime.fromFormat(value, format, { locale: 'en-US' });
  return parsed.isValid && parsed.toFormat(format) === value ? parsed : undefined;
};

export const parseDateSearchParam = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  return parseStrictly(value, DATE_SEARCH_FORMAT)?.toFormat(DATE_SEARCH_FORMAT);
};

export const parseHighlightDate = (value: string): string | undefined =>
  parseStrictly(value, HIGHLIGHT_DATETIME_FORMAT)?.toFormat(DATE_SEARCH_FORMAT);

export const isHighlightDateRangeReversed = ({ from, to }: HighlightDateRange): boolean =>
  !!from && !!to && from > to;

export const filterChaptersByHighlightDate = (
  chapters: ChapterWithHighlights[],
  range: HighlightDateRange
): ChapterWithHighlights[] => {
  const { from, to } = range;
  if ((!from && !to) || isHighlightDateRangeReversed(range)) return chapters;

  return chapters
    .map((chapter) => ({
      ...chapter,
      highlights: chapter.highlights.filter((highlight) => {
        const date = parseHighlightDate(highlight.datetime);
        if (!date) return false;
        return (!from || date >= from) && (!to || date <= to);
      }),
    }))
    .filter((chapter) => chapter.highlights.length > 0);
};

export const getLastSevenDaysFrom = (today: DateTime<boolean> = DateTime.local()): string =>
  today.minus({ days: 6 }).toFormat(DATE_SEARCH_FORMAT);

/**
 * `highlight.datetime` is KOReader's own `yyyy-MM-dd HH:mm:ss` string, passed
 * through rather than normalised to ISO like every other timestamp the API
 * sends. Rendering goes through the app's one formatter, in the browser's
 * locale.
 */
export const formatHighlightDate = (value: string): string => {
  const parsed = parseStrictly(value, HIGHLIGHT_DATETIME_FORMAT);
  if (!parsed) return value;

  return formatDateTime(parsed);
};
