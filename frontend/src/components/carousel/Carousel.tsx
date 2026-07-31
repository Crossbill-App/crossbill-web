import { ArrowBackIcon, ArrowForwardIcon } from '@/theme/Icons.tsx';
import { Box, IconButton, type SxProps, type Theme } from '@mui/material';
import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { useCarouselScroll } from './useCarouselScroll';

/** Width of the edge fade that hints at content beyond the viewport. */
const FADE_PX = 32;

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

const controlSx: SxProps<Theme> = {
  pointerEvents: 'auto',
  mx: 0.5,
  bgcolor: 'background.paper',
  boxShadow: 3,
  '&:hover': { bgcolor: 'background.paper' },
  // Touch devices drag the track directly; buttons would only cover content.
  '@media (hover: none) and (pointer: coarse)': { display: 'none' },
};

export interface CarouselProps {
  children: ReactNode;
  'aria-label': string;
  /** Gap between items, in theme spacing units. */
  gap?: number;
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
export const Carousel = ({ children, 'aria-label': ariaLabel, gap = 2, sx }: CarouselProps) => {
  const { viewportRef, isOverflowing, canScrollBack, canScrollForward, scrollByPage } =
    useCarouselScroll();

  const maskImage = `linear-gradient(to right, transparent 0, #000 ${
    canScrollBack ? FADE_PX : 0
  }px, #000 calc(100% - ${canScrollForward ? FADE_PX : 0}px), transparent 100%)`;

  return (
    <Box sx={[{ position: 'relative', my: -OVERFLOW_PADDING }, ...(Array.isArray(sx) ? sx : [sx])]}>
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
          maskImage,
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
        }}
      >
        <Box component="ul" sx={{ display: 'flex', gap, listStyle: 'none', p: 0, m: 0 }}>
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
            <IconButton aria-label="Scroll back" onClick={() => scrollByPage(-1)} sx={controlSx}>
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
            <IconButton aria-label="Scroll forward" onClick={() => scrollByPage(1)} sx={controlSx}>
              <ArrowForwardIcon />
            </IconButton>
          </motion.div>
        )}
      </AnimatePresence>
    </Box>
  );
};
