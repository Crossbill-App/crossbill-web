import { ArrowBackIcon, ArrowForwardIcon } from '@/theme/Icons.tsx';
import { Box, IconButton, type Breakpoint, type SxProps, type Theme } from '@mui/material';
import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { useCarouselScroll } from './useCarouselScroll';

/**
 * Vertical breathing room inside the scroller, so lifted cards and their
 * shadows are not clipped by the horizontal overflow. Cancelled out again on
 * the wrapper, keeping the component vertically neutral in a layout.
 */
const OVERFLOW_PADDING = 1.5;

const CONTROL_TRANSITION = { duration: 0.15 };

const controlWrapperStyle = (side: 'left' | 'right'): React.CSSProperties => ({
  position: 'absolute',
  top: 0,
  bottom: 0,
  [side]: 0,
  display: 'flex',
  alignItems: 'center',
  pointerEvents: 'none',
  zIndex: 1,
});

/** Inset by the bleed, so the buttons stay on the surrounding content column. */
const controlSx = (bleed: Spacing): SxProps<Theme> => ({
  pointerEvents: 'auto',
  mx: bleed,
  bgcolor: 'background.paper',
  boxShadow: 3,
  '&:hover': { bgcolor: 'background.paper' },
  // Touch devices drag the track directly; buttons would only cover content.
  '@media (hover: none) and (pointer: coarse)': { display: 'none' },
});

type Spacing = number | Partial<Record<Breakpoint, number>>;

const negate = (spacing: Spacing): Spacing =>
  typeof spacing === 'number'
    ? -spacing
    : Object.fromEntries(Object.entries(spacing).map(([key, value]) => [key, -value]));

export interface CarouselProps {
  children: ReactNode;
  'aria-label': string;
  /** Gap between items, in theme spacing units; per-breakpoint if an object. */
  gap?: Spacing;
  /**
   * How far the track may run past its container on each side, in theme spacing
   * units. Set it to the container's own horizontal padding and items scroll to
   * the viewport edge instead of being clipped by the gutter, while the resting
   * first and last item still line up with the surrounding content column.
   */
  bleed?: Spacing;
  sx?: SxProps<Theme>;
}

/**
 * Horizontally scrollable strip of `CarouselItem`s.
 *
 * Scrolling is native, so touch drag, momentum and focus-into-view all behave
 * the way the platform intends. Paging buttons appear only when the content
 * actually overflows, and both paging and the post-drag settle animate onto an
 * item boundary.
 */
export const Carousel = ({
  children,
  'aria-label': ariaLabel,
  gap = 2,
  bleed = 0,
  sx,
}: CarouselProps) => {
  const { viewportRef, isOverflowing, canScrollBack, canScrollForward, scrollByPage } =
    useCarouselScroll();

  return (
    <Box
      sx={[
        { position: 'relative', my: -OVERFLOW_PADDING, mx: negate(bleed) },
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      <Box
        ref={viewportRef}
        role="group"
        aria-label={ariaLabel}
        tabIndex={isOverflowing ? 0 : undefined}
        sx={{
          overflowX: 'auto',
          overflowY: 'clip',
          // Keeps a horizontal drag from triggering the browser's back gesture.
          overscrollBehaviorX: 'contain',
          py: OVERFLOW_PADDING,
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
        }}
      >
        {/* The bleed lives on the track, not the viewport: a scroll container
            leaves its own trailing padding out of the scrollable overflow, so
            padding here is the only way the last item keeps its margin. That
            needs max-content too, or the track fills the viewport and the items
            overflow out of it, stranding the right padding at the fold. */}
        <Box
          component="ul"
          sx={{
            display: 'flex',
            width: 'max-content',
            gap,
            listStyle: 'none',
            m: 0,
            py: 0,
            px: bleed,
          }}
        >
          {children}
        </Box>
      </Box>

      <AnimatePresence>
        {isOverflowing && canScrollBack && (
          <motion.div
            key="back"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={CONTROL_TRANSITION}
            style={controlWrapperStyle('left')}
          >
            <IconButton
              aria-label="Scroll back"
              onClick={() => scrollByPage(-1)}
              sx={controlSx(bleed)}
            >
              <ArrowBackIcon />
            </IconButton>
          </motion.div>
        )}

        {isOverflowing && canScrollForward && (
          <motion.div
            key="forward"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={CONTROL_TRANSITION}
            style={controlWrapperStyle('right')}
          >
            <IconButton
              aria-label="Scroll forward"
              onClick={() => scrollByPage(1)}
              sx={controlSx(bleed)}
            >
              <ArrowForwardIcon />
            </IconButton>
          </motion.div>
        )}
      </AnimatePresence>
    </Box>
  );
};
