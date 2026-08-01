import { Typography } from '@mui/material';
import type { ReactNode } from 'react';

/** Muted placeholder text shown when a list or tab has no content. */
export const EmptyStateText = ({ children }: { children: ReactNode }) => (
  <Typography
    variant="body2"
    sx={{
      color: 'text.secondary',
    }}
  >
    {children}
  </Typography>
);
