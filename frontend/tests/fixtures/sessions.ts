import type { BookReadingStatistics, ReadingSession } from '@/api/generated/model';

export const aReadingSession = (overrides: Partial<ReadingSession> = {}): ReadingSession => ({
  id: 200,
  book_id: 1,
  device_id: 'kindle-1',
  content_hash: 'hash',
  start_time: '2026-10-12T19:30:00Z',
  end_time: '2026-10-12T20:41:00Z',
  start_page: 102,
  end_page: 115,
  created_at: '2026-10-12T20:41:00Z',
  highlights: [],
  ...overrides,
});

export const aBookStatistics = (
  overrides: Partial<BookReadingStatistics> = {}
): BookReadingStatistics => ({
  session_count: 12,
  total_reading_seconds: 8 * 3600 + 25 * 60,
  average_session_seconds: 42 * 60,
  first_session_start: '2026-09-01T18:00:00Z',
  last_session_end: '2026-10-12T20:41:00Z',
  span_days: 42,
  progress_percent: 63,
  ...overrides,
});
