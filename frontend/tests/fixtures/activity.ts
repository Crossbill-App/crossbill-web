import type { LibraryActivity, LibraryStats } from '@/api/generated/model';

/**
 * A library's activity grid, empty unless a test fills it in. The window is a
 * year ending on the last day anything was read, as the backend's is.
 */
export const aReadingActivity = (overrides: Partial<LibraryActivity> = {}): LibraryActivity => ({
  unit: 'pages',
  range_start: '2025-09-01',
  range_end: '2026-09-01',
  days: [],
  books: [],
  ...overrides,
});

/**
 * The numbers beside a library's grid. A quiet reader by default: nothing read
 * today, so a test that cares about a figure names the one it cares about.
 */
export const aReadingSummary = (overrides: Partial<LibraryStats> = {}): LibraryStats => ({
  last_read: '2026-09-01',
  seconds_today: 0,
  total_seconds: 0,
  streak_days: 0,
  days_read: 0,
  books_read: 0,
  ...overrides,
});
