import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

/** The contract between an item and `useCarouselScroll`'s paging maths. */
export const CAROUSEL_ITEM_SELECTOR = '[data-carousel-item]';

export interface CarouselItemProps {
  children: ReactNode;
  sx?: SxProps<Theme>;
}

/** A single slide; the `data-` attribute is what paging aligns against. */
export const CarouselItem = ({ children, sx }: CarouselItemProps) => (
  <Box
    component="li"
    data-carousel-item=""
    sx={[{ flex: '0 0 auto' }, ...(Array.isArray(sx) ? sx : [sx])]}
  >
    {children}
  </Box>
);
