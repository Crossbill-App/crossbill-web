import type { RecentCapture } from '@/api/generated/model';

/** A highlight in the dashboard's capture feed, with the day and time it was marked. */
export const aCapturedHighlight = (overrides: Partial<RecentCapture> = {}): RecentCapture => ({
  kind: 'highlight',
  id: 300,
  book_id: 1,
  book_title: 'Bullshit Jobs',
  chapter_name: 'Chapter One',
  title: null,
  text: 'The map is not the territory.',
  note_kind: null,
  page: 42,
  label: null,
  captured_at: '2026-08-30T20:00:00',
  day: '2026-08-30',
  more_in_book: 0,
  ...overrides,
});

/** A note in the same feed, filed under its latest edit. */
export const aCapturedNote = (overrides: Partial<RecentCapture> = {}): RecentCapture => ({
  ...aCapturedHighlight(),
  kind: 'note',
  id: 400,
  title: 'Ada Lovelace',
  text: 'The first programmer.',
  note_kind: 'character',
  chapter_name: null,
  page: null,
  ...overrides,
});
