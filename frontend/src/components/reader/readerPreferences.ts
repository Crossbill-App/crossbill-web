import type { Theme } from '@mui/material/styles';
import { EpubPreferences, TextAlignment, type IEpubPreferences } from '@readium/navigator';

/** The reading themes the settings popover offers, in the order it shows them. */
export const READER_THEMES = ['light', 'sepia', 'dark'] as const;

export type ReaderThemeName = (typeof READER_THEMES)[number];

/** Sentence-case, because these are user-facing labels on the theme control. */
export const READER_THEME_LABELS: Record<ReaderThemeName, string> = {
  light: 'Light',
  sepia: 'Sepia',
  dark: 'Dark',
};

/**
 * How lines are set, as the popover offers it.
 *
 * Three states rather than a switch, because the honest default is neither of
 * the other two: ReadiumCSS leaves `text-align` to the book's own stylesheet
 * until a reader overrides it, and a binary control would have to pick one of
 * them for everybody and quietly re-set every book in the library.
 */
export const READER_ALIGNMENTS = ['default', 'left', 'justified'] as const;

export type ReaderAlignment = (typeof READER_ALIGNMENTS)[number];

export const READER_ALIGNMENT_LABELS: Record<ReaderAlignment, string> = {
  default: 'Default',
  left: 'Left',
  justified: 'Justified',
};

/**
 * What each alignment is in the navigator's terms, `null` being "say nothing
 * and let the book decide".
 *
 * `start` rather than `left`: in a right-to-left book the ragged edge belongs
 * on the right, and only `start` follows the publication's own progression.
 */
const READIUM_ALIGNMENTS: Record<ReaderAlignment, TextAlignment | null> = {
  default: null,
  left: TextAlignment.start,
  justified: TextAlignment.justify,
};

/** Which alignment a navigator preference is, for reading one back out of storage. */
export const alignmentOf = (value: TextAlignment | null | undefined): ReaderAlignment =>
  READER_ALIGNMENTS.find((name) => READIUM_ALIGNMENTS[name] === value) ?? 'default';

/** One column, whatever the viewport could have fitted. */
export const SINGLE_COLUMN = 1;

/**
 * As many columns as the width allows, which is what Readium does when nobody
 * has asked for a number.
 */
const AUTOMATIC_COLUMNS = null;

export interface ReaderPreferences {
  theme: ReaderThemeName;
  /**
   * A multiplier on the publication's own font size, which is how Readium
   * states it — 1 is the book as its publisher set it.
   */
  fontSize: number;
  alignment: ReaderAlignment;
  /**
   * One column even where the viewport has room for two. Below the `sm`
   * breakpoint there is only ever room for one, so the setting is real but
   * inert there and the control is not offered.
   */
  singleColumn: boolean;
}

export const DEFAULT_READER_PREFERENCES: ReaderPreferences = {
  theme: 'light',
  fontSize: 1,
  alignment: 'default',
  singleColumn: false,
};

/** The page colours of a reading theme, for the reader's chrome and its content alike. */
export const readerPageColors = (theme: Theme, name: ReaderThemeName) =>
  theme.customColors.readerPage[name];

/**
 * The half of the reader's preferences the navigator owns outright — every
 * setting except the page colours, which the reading theme decides.
 *
 * Split out because this is also the half worth *storing*: colours are derived
 * from a theme name and would only go stale in a browser's storage.
 */
export const toTypographyPreferences = (preferences: ReaderPreferences): IEpubPreferences => ({
  fontSize: preferences.fontSize,
  textAlign: READIUM_ALIGNMENTS[preferences.alignment],
  columnCount: preferences.singleColumn ? SINGLE_COLUMN : AUTOMATIC_COLUMNS,
});

/**
 * Translates our settings into the preferences the navigator understands.
 *
 * Deliberately a small surface: `EpubPreferences` has forty-odd fields, and
 * every one we set is one the reader can no longer inherit from the book. The
 * two that can be *unset* are sent as `null` rather than omitted — the
 * navigator merges preferences into the ones it already holds and skips
 * whatever is `undefined`, so an omitted field is not a reset.
 */
export const toEpubPreferences = (
  theme: Theme,
  preferences: ReaderPreferences
): EpubPreferences => {
  const colors = readerPageColors(theme, preferences.theme);
  return new EpubPreferences({
    ...toTypographyPreferences(preferences),
    backgroundColor: colors.background,
    textColor: colors.text,
  });
};
