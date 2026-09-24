import { aChapter, aHighlight } from '@tests/fixtures/book';
import { DateTime } from 'luxon';
import { expect, test } from 'vitest';
import {
  filterChaptersByHighlightDate,
  getLastSevenDaysFrom,
  parseDateSearchParam,
  type HighlightDateRange,
} from './highlightDates.ts';

const chapters = [
  aChapter({
    id: 10,
    highlights: [
      aHighlight({ id: 1, datetime: '2026-07-04T23:59:59' }),
      aHighlight({ id: 2, datetime: '2026-07-05T00:00:00' }),
      aHighlight({ id: 3, datetime: '2026-07-05T23:59:59' }),
      aHighlight({ id: 4, datetime: '2026-07-06T00:00:00' }),
      aHighlight({ id: 5, datetime: 'legacy timestamp' }),
    ],
  }),
  aChapter({
    id: 20,
    highlights: [aHighlight({ id: 6, chapter_id: 20, datetime: '2026-07-01T12:00:00' })],
  }),
];

const highlightIds = (range: HighlightDateRange) =>
  filterChaptersByHighlightDate(chapters, range).map((chapter) => ({
    chapterId: chapter.id,
    highlightIds: chapter.highlights.map((highlight) => highlight.id),
  }));

test('a From bound is inclusive and a malformed timestamp is filtered out', () => {
  expect(highlightIds({ from: '2026-07-05' })).toEqual([
    { chapterId: 10, highlightIds: [2, 3, 4] },
  ]);
});

test('parses only canonical search dates', () => {
  expect(parseDateSearchParam('2026-07-05')).toBe('2026-07-05');
  expect(parseDateSearchParam('2026-7-5')).toBeUndefined();
  expect(parseDateSearchParam('2026-02-30')).toBeUndefined();
  expect(parseDateSearchParam('2026-07-05T23:59:59')).toBeUndefined();
  expect(parseDateSearchParam(['2026-07-05'])).toBeUndefined();
});

test('calculates a snapshot lower bound covering today and the preceding six dates', () => {
  expect(getLastSevenDaysFrom(DateTime.fromISO('2026-08-26T15:00:00'))).toBe('2026-08-20');
});
