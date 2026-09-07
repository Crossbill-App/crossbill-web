import type { Theme } from '@mui/material/styles';
import { EpubPreferences } from '@readium/navigator';

/** The reading themes the settings popover offers, in the order it shows them. */
export const READER_THEMES = ['light', 'sepia', 'dark'] as const;

export type ReaderThemeName = (typeof READER_THEMES)[number];

/** Sentence-case, because these are user-facing labels on the theme control. */
export const READER_THEME_LABELS: Record<ReaderThemeName, string> = {
  light: 'Light',
  sepia: 'Sepia',
  dark: 'Dark',
};

export interface ReaderPreferences {
  theme: ReaderThemeName;
  /**
   * A multiplier on the publication's own font size, which is how Readium
   * states it — 1 is the book as its publisher set it.
   */
  fontSize: number;
}

export const DEFAULT_READER_PREFERENCES: ReaderPreferences = { theme: 'light', fontSize: 1 };

/** The page colours of a reading theme, for the reader's chrome and its content alike. */
export const readerPageColors = (theme: Theme, name: ReaderThemeName) =>
  theme.customColors.readerPage[name];

/**
 * Translates our two settings into the preferences the navigator understands.
 *
 * Deliberately a small surface: `EpubPreferences` has forty-odd fields, and
 * every one we set is one the reader can no longer inherit from the book.
 */
export const toEpubPreferences = (
  theme: Theme,
  preferences: ReaderPreferences
): EpubPreferences => {
  const colors = readerPageColors(theme, preferences.theme);
  return new EpubPreferences({
    backgroundColor: colors.background,
    textColor: colors.text,
    fontSize: preferences.fontSize,
  });
};
