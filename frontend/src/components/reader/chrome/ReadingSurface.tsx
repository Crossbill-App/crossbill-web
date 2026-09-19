import { ReaderLoading } from '@/components/reader/chrome/ReaderLoading.tsx';
import { readerControlSx } from '@/components/reader/chrome/readerOverlay.ts';
import type { readerPageColors } from '@/components/reader/preferences/readerPreferences.ts';
import { NextPageIcon, PreviousPageIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import { Box, IconButton, Stack, Typography } from '@mui/material';
import type { ReactNode, RefObject } from 'react';

/** The width the page-turn buttons need beside the text on anything but a phone. */
const PAGE_TURN_GUTTER = '48px';

/** Readium's own page gutter is horizontal only, so the air above and below is ours to add. */
const READING_SURFACE_INSET = 4;

interface PageTurnButtonProps {
  edge: 'left' | 'right';
  onClick: () => void;
  disabled: boolean;
  /** The page's, for the same reason the toolbar above takes them. */
  colors: ReturnType<typeof readerPageColors>;
}

const PageTurnButton = ({ edge, onClick, disabled, colors }: PageTurnButtonProps) => (
  <IconButton
    onClick={onClick}
    disabled={disabled}
    color="inherit"
    aria-label={edge === 'left' ? 'Previous page' : 'Next page'}
    sx={{
      position: 'absolute',
      top: '50%',
      transform: 'translateY(-50%)',
      [edge]: 4,
      zIndex: 1,
      // Gone on a phone, where they cover the page they turn and swiping is
      // the gesture at hand; the gutter they need goes with them.
      display: { xs: 'none', sm: 'inline-flex' },
      ...readerControlSx(colors),
    }}
  >
    {edge === 'left' ? (
      <PreviousPageIcon sx={{ fontSize: ICON_SIZE.prominent }} />
    ) : (
      <NextPageIcon sx={{ fontSize: ICON_SIZE.prominent }} />
    )}
  </IconButton>
);

export interface ReadingSurfaceProps {
  /** The box the engine lays the book out in. */
  host: RefObject<HTMLDivElement | null>;
  isOpen: boolean;
  /** A lapsed cookie being replaced: the page is held behind a word about it. */
  isRenewing: boolean;
  colors: ReturnType<typeof readerPageColors>;
  onNext: () => void;
  onPrevious: () => void;
  /** What the live region above the page has to say, if anything. */
  notice?: ReactNode;
}

/** The page itself: the book's own box, the ways to turn it, and what is said over it. */
export const ReadingSurface = ({
  host,
  isOpen,
  isRenewing,
  colors,
  onNext,
  onPrevious,
  notice,
}: ReadingSurfaceProps) => {
  const pageTurnsDisabled = isRenewing || !isOpen;

  return (
    <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
      <PageTurnButton
        edge="left"
        onClick={onPrevious}
        disabled={pageTurnsDisabled}
        colors={colors}
      />
      <PageTurnButton edge="right" onClick={onNext} disabled={pageTurnsDisabled} colors={colors} />

      {/* Hidden rather than unmounted: the engine measures this box to lay
          the book out, and a box that is not there has no size to measure. */}
      <Box
        ref={host}
        sx={{
          height: '100%',
          px: { xs: 0, sm: PAGE_TURN_GUTTER },
          py: READING_SURFACE_INSET,
          visibility: isOpen ? 'visible' : 'hidden',
        }}
      />

      {!isOpen && <ReaderLoading />}

      {/* Mounted for as long as the book is, because a live region appearing
          together with its words announces nothing. At the top: the sides belong
          to the page-turn buttons and the bottom to a phone's own callout. */}
      {isOpen && (
        <Box
          aria-live="polite"
          sx={{
            position: 'absolute',
            top: (t) => t.spacing(1),
            left: '50%',
            transform: 'translateX(-50%)',
            maxWidth: '100%',
            zIndex: 2,
          }}
        >
          {notice}
        </Box>
      )}

      {/* Mounted for as long as the book is: a live region that appears
          together with its text announces nothing. */}
      {isOpen && (
        <Stack
          aria-live="polite"
          sx={{
            position: 'absolute',
            inset: 0,
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: isRenewing ? 'auto' : 'none',
            ...(isRenewing && { backgroundColor: colors.background, opacity: 0.9 }),
          }}
        >
          {isRenewing && <Typography variant="body2">Reconnecting…</Typography>}
        </Stack>
      )}
    </Box>
  );
};
