import type { SxProps, Theme } from '@mui/material';

export const overlaySx: SxProps<Theme> = {
  position: 'fixed',
  inset: 0,
  zIndex: (t) => t.zIndex.appBar + 1,
  display: 'flex',
  flexDirection: 'column',
};
