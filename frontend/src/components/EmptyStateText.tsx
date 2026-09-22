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

/**
 * Muted placeholder text shown when a list or tab has no content.
 *
 * `role="status"` because an empty state is a state, not decoration: it is what
 * a filter that excluded everything has to announce, and it is the handle a
 * test asks for the state by, instead of quoting the sentence back.
 */
export const EmptyStateText = ({ children, variant = 'inline' }: EmptyStateTextProps) => (
  <Typography
    role="status"
    variant={variant === 'page' ? 'body1' : 'body2'}
    sx={{
      color: 'text.secondary',
      ...(variant === 'page' && { py: 4, textAlign: 'center' }),
    }}
  >
    {children}
  </Typography>
);
