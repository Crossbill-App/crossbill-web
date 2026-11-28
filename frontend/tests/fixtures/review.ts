import type { DueFlashcard } from '@/api/generated/model';
import { aFlashcard } from './book';

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

const fromNow = (milliseconds: number) => new Date(Date.now() + milliseconds).toISOString();

export const aDueFlashcard = (overrides: Partial<DueFlashcard> = {}): DueFlashcard => ({
  ...aFlashcard(),
  book_title: 'The Pragmatic Reader',
  chapter_name: 'On Attention',
  highlight_text: 'Attention is the gate of memory.',
  note_title: null,
  previews: {
    again: fromNow(8 * HOUR),
    hard: fromNow(DAY),
    good: fromNow(3 * DAY),
    easy: fromNow(60 * DAY),
  },
  ...overrides,
});
