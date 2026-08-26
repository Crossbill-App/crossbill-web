import type { ChapterWithHighlights } from '@/api/generated/model';
import { DateTime } from 'luxon';

export const DATE_SEARCH_FORMAT = 'yyyy-MM-dd';
const HIGHLIGHT_DATETIME_FORMAT = 'yyyy-MM-dd HH:mm:ss';

export interface HighlightDateRange {
  from?: string;
  to?: string;
}

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

export const formatHighlightDate = (value: string): string => {
  const parsed = parseStrictly(value, HIGHLIGHT_DATETIME_FORMAT);
  if (!parsed) return value;

  return parsed.setLocale('en-US').toLocaleString({
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};
