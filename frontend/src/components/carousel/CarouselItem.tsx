import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

export interface CarouselItemProps {
  children: ReactNode;
  sx?: SxProps<Theme>;
}

/** A single slide. The `data-` attribute is how `Carousel` finds snap targets. */
export const CarouselItem = ({ children, sx }: CarouselItemProps) => (
  <Box
    component="li"
    data-carousel-item=""
    sx={[{ flex: '0 0 auto' }, ...(Array.isArray(sx) ? sx : [sx])]}
  >
    {children}
  </Box>
);
