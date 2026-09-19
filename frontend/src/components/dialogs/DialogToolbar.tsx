import { COARSE_POINTER_QUERY, TOUCH_TARGET_MIN } from '@/theme/theme.ts';
import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

const MEDIUM_ICON_SIZE = 24;

interface DialogToolbarProps {
  children: ReactNode;
  sx?: SxProps<Theme>;
}

/** Right-aligned action row used by the entity detail modals' toolbars. */
export const DialogToolbar = ({ children, sx }: DialogToolbarProps) => (
  <Box
    sx={[
      {
        display: 'flex',
        justifyContent: 'flex-end',
        // Icon buttons space themselves with their padding; bordered text buttons would touch.
        '& > .MuiButton-root + .MuiButton-root': { ml: 1 },
        // The last icon lines up with the gutter, not its button's padding. MUI's
        // edge="end" is a fixed -12px, which overshoots the 8px desktop padding.
        '& > .MuiIconButton-root:last-child': {
          mr: -1,
          [COARSE_POINTER_QUERY]: { mr: `${-(TOUCH_TARGET_MIN - MEDIUM_ICON_SIZE) / 2}px` },
        },
      },
      ...(Array.isArray(sx) ? sx : [sx]),
    ]}
  >
    {children}
  </Box>
);
