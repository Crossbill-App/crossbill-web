import { Box } from '@mui/material';
import type { ReactNode } from 'react';

/** Soft length guide for a gist: a counter, never a hard limit. */
const GIST_LENGTH_GUIDE = 200;

interface GistHelperTextProps {
  length: number;
  /** Optional text on the left of the counter — a prompt or an error. */
  message?: ReactNode;
}

/**
 * Helper row under a gist field: an optional message on the left, the
 * character count against `GIST_LENGTH_GUIDE` on the right. Shared so the
 * inline gist editor and the note dialog show the same guide.
 */
export const GistHelperText = ({ length, message }: GistHelperTextProps) => (
  <Box component="span" sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
    <span>{message}</span>
    <Box
      component="span"
      sx={{ flexShrink: 0, color: length > GIST_LENGTH_GUIDE ? 'warning.main' : 'inherit' }}
    >
      {length}/{GIST_LENGTH_GUIDE}
    </Box>
  </Box>
);
