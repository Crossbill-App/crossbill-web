import type { EbookAppearance } from '@/components/reader/EbookReader.ts';
import type { Theme } from '@mui/material/styles';

/** The page colours the reader can choose between. */
export const READER_PAGE_COLORS = ['light', 'dark'] as const;
export type ReaderPageColor = (typeof READER_PAGE_COLORS)[number];
export const READER_PAGE_COLOR_LABELS: Record<ReaderPageColor, string> = {
  light: 'Light',
  dark: 'Dark',
};

/** How far apart the lines are set, `default` leaving the book's own spacing alone. */
export const READER_LINE_HEIGHTS = ['tight', 'default', 'loose'] as const;
type ReaderLineHeight = (typeof READER_LINE_HEIGHTS)[number];
export const READER_LINE_HEIGHT_LABELS: Record<ReaderLineHeight, string> = {
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
  lineHeight: ReaderLineHeight;
  alignment: ReaderAlignment;
  columns: ReaderColumns;
}

export const DEFAULT_READER_PREFERENCES: ReaderPreferences = {
  pageColor: 'light',
  fontSize: 1,
  lineHeight: 'default',
  alignment: 'default',
  columns: 'single',
};

const LINE_HEIGHTS: Record<ReaderLineHeight, EbookAppearance['lineHeight']> = {
  tight: 1.2,
  default: null,
  loose: 1.8,
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
    lineHeight: LINE_HEIGHTS[preferences.lineHeight],
    textAlign: TEXT_ALIGNMENTS[preferences.alignment],
    columnCount: preferences.columns === 'single' ? 1 : null,
    pageBackgroundColor: colors.background,
    pageTextColor: colors.text,
  };
};
