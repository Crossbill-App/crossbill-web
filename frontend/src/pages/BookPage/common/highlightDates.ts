import type { ChapterWithHighlights } from '@/api/generated/model';
import { DateTime } from 'luxon';

export const DATE_SEARCH_FORMAT = 'yyyy-MM-dd';

export interface HighlightDateRange {
  from?: string;
  to?: string;
}

/**
 * The calendar day an ISO timestamp falls on, as `yyyy-MM-dd`.
 *
 * `toISODate` is ISO output rather than a locale rendering, so it stays in
 * ASCII digits whatever numbering system the reader's locale uses.
 */
const isoDay = (value: string): string | undefined =>
  DateTime.fromISO(value).toISODate() ?? undefined;

export const parseDateSearchParam = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const day = isoDay(value);
  return day === value ? day : undefined;
};

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
        const date = isoDay(highlight.datetime);
        if (!date) return false;
        return (!from || date >= from) && (!to || date <= to);
      }),
    }))
    .filter((chapter) => chapter.highlights.length > 0);
};

export const getLastSevenDaysFrom = (today: DateTime<boolean> = DateTime.local()): string =>
  today.minus({ days: 6 }).toFormat(DATE_SEARCH_FORMAT);
