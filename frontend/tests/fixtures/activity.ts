import type { LibraryActivity } from '@/api/generated/model';

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
