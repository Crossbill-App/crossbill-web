import type { readerPageColors } from '@/components/reader/preferences/readerPreferences.ts';
import { alpha, type SxProps, type Theme } from '@mui/material';

export const overlaySx: SxProps<Theme> = {
  position: 'fixed',
  inset: 0,
  zIndex: (t) => t.zIndex.appBar + 1,
  display: 'flex',
  flexDirection: 'column',
};

/** The wash under a hovered control, at the strength MUI's own dark palette uses. */
const HOVER_OPACITY = 0.08;

/**
 * A control that cannot be used, still readable as one. MUI's `action.disabled`
 * is black at 26%, which on the dark page is a button that has vanished rather
 * than one that is waiting.
 */
const DISABLED_OPACITY = 0.35;

/**
 * How a control drawn on the book's page answers the pointer and the keyboard.
 *
 * `IconButton` states every one of these over the app's light surfaces — a
 * black wash on hover, an amber focus ring, a black glyph while disabled — and
 * the reader's page is not one of them: its colour is the reader's to choose.
 * Paired with `color="inherit"`, which is what puts the glyph itself in the
 * page's colour and so gives the ripple and the ring a `currentColor` worth
 * taking.
 */
export const readerControlSx = (colors: ReturnType<typeof readerPageColors>): SxProps<Theme> => ({
  '&:hover': { backgroundColor: alpha(colors.text, HOVER_OPACITY) },
  // `IconButton`'s own reset, which its `--IconButton-hoverBg` rule would have
  // applied: a tap on a touch screen must not leave the wash behind it.
  '@media (hover: none)': { '&:hover': { backgroundColor: 'transparent' } },
  '&:focus-visible': { outlineColor: 'currentColor' },
  '&.Mui-disabled': { color: alpha(colors.text, DISABLED_OPACITY) },
});
