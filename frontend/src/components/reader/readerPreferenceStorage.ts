import {
  alignmentOf,
  DEFAULT_READER_PREFERENCES,
  READER_THEMES,
  SINGLE_COLUMN,
  toTypographyPreferences,
  type ReaderPreferences,
  type ReaderThemeName,
} from '@/components/reader/readerPreferences.ts';
import { EpubPreferences } from '@readium/navigator';

/**
 * Where the reader's appearance is remembered, and the only key this app puts
 * in a browser's storage.
 *
 * One key for the whole library rather than one per book. Font size, page
 * colour, alignment and column count are facts about the person reading and
 * the screen they are reading on — somebody who needs larger text needs it in
 * every book they open, and a per-book setting would mean setting it again for
 * each of them. Nothing here is a fact about a book.
 */
export const READER_PREFERENCES_KEY = 'crossbill.reader.preferences';

/**
 * The version of the shape stored under that key.
 *
 * Bumped whenever what the popover controls stops being expressible in what is
 * already written down. Anything answering to another version is left alone
 * and the reader gets the defaults, which is the same silence a first-time
 * reader gets rather than an error about a browser's storage.
 */
const STORAGE_VERSION = 1;

interface StoredPreferences {
  version: number;
  /** The reading theme's name. Ours: Readium knows colours, not themes. */
  theme: string;
  /**
   * The navigator's own serialisation of everything else, so the stored shape
   * tracks the library rather than a hand-copy of it. It is also the
   * validation: `EpubPreferences` re-checks every field it parses — a font
   * size outside the supported range, an alignment that is not one of the
   * four, a negative column count — and drops whatever it cannot use.
   */
  epub: string;
}

const storedTheme = (value: unknown): ReaderThemeName =>
  READER_THEMES.find((name) => name === value) ?? DEFAULT_READER_PREFERENCES.theme;

/**
 * The reader's remembered appearance, or the defaults.
 *
 * Every way this can go wrong ends in the same place, silently: storage a
 * browser refuses to hand over (a private window, third-party cookies
 * blocked), nothing written yet, a shape from another version, or text that is
 * not the JSON it claims to be. None of those is worth a word to somebody who
 * came here to read a book, and all of them leave a perfectly usable reader.
 */
export const loadReaderPreferences = (): ReaderPreferences => {
  try {
    const raw = window.localStorage.getItem(READER_PREFERENCES_KEY);
    if (raw === null) return DEFAULT_READER_PREFERENCES;

    const stored = JSON.parse(raw) as Partial<StoredPreferences> | null;
    if (stored?.version !== STORAGE_VERSION || typeof stored.epub !== 'string') {
      return DEFAULT_READER_PREFERENCES;
    }

    const epub = EpubPreferences.deserialize(stored.epub);
    if (!epub) return DEFAULT_READER_PREFERENCES;

    return {
      theme: storedTheme(stored.theme),
      fontSize: epub.fontSize ?? DEFAULT_READER_PREFERENCES.fontSize,
      alignment: alignmentOf(epub.textAlign),
      singleColumn: epub.columnCount === SINGLE_COLUMN,
    };
  } catch {
    // Storage that throws on being read at all, or a value that is not JSON.
    return DEFAULT_READER_PREFERENCES;
  }
};

/** Writes the reader's appearance down, where the browser lets us. */
export const saveReaderPreferences = (preferences: ReaderPreferences): void => {
  try {
    const stored: StoredPreferences = {
      version: STORAGE_VERSION,
      theme: preferences.theme,
      epub: EpubPreferences.serialize(new EpubPreferences(toTypographyPreferences(preferences))),
    };
    window.localStorage.setItem(READER_PREFERENCES_KEY, JSON.stringify(stored));
  } catch {
    // Storage turned off, or a quota that is full. The reader behaves exactly
    // as it did; it just will not remember this the next time a book is opened.
  }
};
