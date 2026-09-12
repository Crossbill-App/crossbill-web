import type { EbookAppearance } from '@/components/reader/EbookReader.ts';
import type { Theme } from '@mui/material/styles';

/** The page colours the reader can choose between. */
export const READER_PAGE_COLORS = ['light', 'dark'] as const;
export type ReaderPageColor = (typeof READER_PAGE_COLORS)[number];
export const READER_PAGE_COLOR_LABELS: Record<ReaderPageColor, string> = {
  light: 'Light',
  dark: 'Dark',
};

/** How far apart the text is set, `default` leaving the book's own spacing alone. */
export const READER_SPACINGS = ['tight', 'default', 'loose'] as const;
type ReaderSpacing = (typeof READER_SPACINGS)[number];
export const READER_SPACING_LABELS: Record<ReaderSpacing, string> = {
  tight: 'Tight',
  default: 'Default',
  loose: 'Loose',
};

/** How lines are set, `default` leaving the book's own stylesheet in charge. */
export const READER_ALIGNMENTS = ['default', 'left', 'justified'] as const;
type ReaderAlignment = (typeof READER_ALIGNMENTS)[number];
export const READER_ALIGNMENT_LABELS: Record<ReaderAlignment, string> = {
  default: 'Default',
  left: 'Left',
  justified: 'Justified',
};

/** How many columns the page is set in. */
export const READER_COLUMNS = ['single', 'auto'] as const;
type ReaderColumns = (typeof READER_COLUMNS)[number];
export const READER_COLUMN_LABELS: Record<ReaderColumns, string> = {
  single: '1 column',
  auto: 'Auto',
};

export interface ReaderPreferences {
  pageColor: ReaderPageColor;
  fontSize: number;
  spacing: ReaderSpacing;
  alignment: ReaderAlignment;
  columns: ReaderColumns;
}

export const DEFAULT_READER_PREFERENCES: ReaderPreferences = {
  pageColor: 'light',
  fontSize: 1,
  spacing: 'default',
  alignment: 'default',
  columns: 'single',
};

// Tight leaves the paragraph breaks alone rather than closing them to 0: a book
// that separates its paragraphs by spacing alone would run them together.
const SPACINGS: Record<
  ReaderSpacing,
  Pick<EbookAppearance, 'lineHeight' | 'paragraphSpacing' | 'paragraphIndent'>
> = {
  tight: { lineHeight: 1.2, paragraphSpacing: null, paragraphIndent: null },
  default: { lineHeight: null, paragraphSpacing: null, paragraphIndent: null },
  loose: { lineHeight: 1.8, paragraphSpacing: 1, paragraphIndent: 1 },
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
    ...SPACINGS[preferences.spacing],
    textAlign: TEXT_ALIGNMENTS[preferences.alignment],
    columnCount: preferences.columns === 'single' ? 1 : null,
    pageBackgroundColor: colors.background,
    pageTextColor: colors.text,
  };
};
