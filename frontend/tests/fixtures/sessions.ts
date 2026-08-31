import type { ReadingSession } from '@/api/generated/model';

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
