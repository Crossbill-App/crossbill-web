import { Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface EmptyStateTextProps {
  children: ReactNode;
  /**
   * `page` centres the message with room around it, for a whole page or tab
   * with nothing in it. `inline`, the default, sits in the flow of a sidebar
   * section or a dialog panel.
   */
  variant?: 'inline' | 'page';
}

/** Muted placeholder text shown when a list or tab has no content. */
export const EmptyStateText = ({ children, variant = 'inline' }: EmptyStateTextProps) => (
  <Typography
    variant={variant === 'page' ? 'body1' : 'body2'}
    sx={{
      color: 'text.secondary',
      ...(variant === 'page' && { py: 4, textAlign: 'center' }),
    }}
  >
    {children}
  </Typography>
);
