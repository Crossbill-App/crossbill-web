import type { EbookAppearance } from '@/components/reader/EbookReader.ts';
import type { Theme } from '@mui/material/styles';

/** The page colours the reader can choose between. */
export type ReaderPageColor = 'light' | 'dark';

/** How lines are set, `default` leaving the book's own stylesheet in charge. */
type ReaderAlignment = 'default' | 'left' | 'justified';

/** How many columns the page is set in. */
type ReaderColumns = 'single' | 'auto';

export interface ReaderPreferences {
  pageColor: ReaderPageColor;
  fontSize: number;
  alignment: ReaderAlignment;
  columns: ReaderColumns;
}

export const DEFAULT_READER_PREFERENCES: ReaderPreferences = {
  pageColor: 'light',
  fontSize: 1,
  alignment: 'default',
  columns: 'single',
};

// `left` is `start`: in a right-to-left book the ragged edge belongs on the
// right, and only `start` follows the publication's own reading progression.
const TEXT_ALIGNMENTS: Record<ReaderAlignment, EbookAppearance['textAlign']> = {
  default: null,
  left: 'start',
  justified: 'justify',
};

/** The page colours of one reading colour, for the reader's chrome and its content alike. */
export const readerPageColors = (theme: Theme, name: ReaderPageColor) =>
  theme.customColors.readerPage[name];

/** What the reader chose, in the terms the seam carries. */
export const toEbookAppearance = (
  theme: Theme,
  preferences: ReaderPreferences
): EbookAppearance => {
  const colors = readerPageColors(theme, preferences.pageColor);
  return {
    fontSize: preferences.fontSize,
    textAlign: TEXT_ALIGNMENTS[preferences.alignment],
    columnCount: preferences.columns === 'single' ? 1 : null,
    pageBackgroundColor: colors.background,
    pageTextColor: colors.text,
  };
};
