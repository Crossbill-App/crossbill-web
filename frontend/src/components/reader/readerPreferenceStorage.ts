import {
  DEFAULT_READER_PREFERENCES,
  READER_ALIGNMENTS,
  READER_COLUMNS,
  READER_PAGE_COLORS,
  READER_SPACINGS,
  type ReaderPreferences,
} from '@/components/reader/readerPreferences.ts';
import { fontSizeRangeConfig } from '@readium/navigator';

/** Where the reader's appearance is remembered: one key for the whole library. */
export const READER_PREFERENCES_KEY = 'crossbill.reader.preferences';

// Bumped whenever what the popover controls stops being expressible in what is
// already written down, so a record of another shape is recognised, not half-read.
const STORAGE_VERSION = 1;

interface StoredPreferences extends ReaderPreferences {
  version: number;
}

const storedRecord = (): Partial<StoredPreferences> | null => {
  try {
    const raw = window.localStorage.getItem(READER_PREFERENCES_KEY);
    if (raw === null) return null;
    return JSON.parse(raw) as Partial<StoredPreferences> | null;
  } catch {
    // Storage the browser refuses to hand over, or text that is not JSON.
    return null;
  }
};

const offered = <T extends string>(options: readonly T[], value: unknown, fallback: T): T =>
  options.find((option) => option === value) ?? fallback;

const storedFontSize = (value: unknown): number => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return DEFAULT_READER_PREFERENCES.fontSize;
  }
  const [min, max] = fontSizeRangeConfig.range;
  return Math.min(Math.max(value, min), max);
};

/**
 * The reader's remembered appearance, or the defaults wherever it cannot be read.
 *
 * Silently: none of the ways this goes wrong is worth a word to somebody who
 * came here to read a book, and each one leaves a perfectly usable reader.
 */
export const loadReaderPreferences = (): ReaderPreferences => {
  const stored = storedRecord();
  if (stored?.version !== STORAGE_VERSION) return DEFAULT_READER_PREFERENCES;
  return {
    pageColor: offered(READER_PAGE_COLORS, stored.pageColor, DEFAULT_READER_PREFERENCES.pageColor),
    fontSize: storedFontSize(stored.fontSize),
    spacing: offered(READER_SPACINGS, stored.spacing, DEFAULT_READER_PREFERENCES.spacing),
    alignment: offered(READER_ALIGNMENTS, stored.alignment, DEFAULT_READER_PREFERENCES.alignment),
    columns: offered(READER_COLUMNS, stored.columns, DEFAULT_READER_PREFERENCES.columns),
  };
};

/** Writes the appearance down, where the browser allows it. */
export const saveReaderPreferences = (preferences: ReaderPreferences): void => {
  try {
    // A record from a newer build reads as the defaults above, so overwriting
    // one would make the version field cause the very loss it exists to prevent.
    const existing = storedRecord()?.version;
    if (typeof existing === 'number' && existing > STORAGE_VERSION) return;

    const stored: StoredPreferences = { version: STORAGE_VERSION, ...preferences };
    window.localStorage.setItem(READER_PREFERENCES_KEY, JSON.stringify(stored));
  } catch {
    // Storage turned off, or full.
  }
};
