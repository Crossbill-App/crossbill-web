import type { SxProps, Theme } from '@mui/material';
import { Typography } from '@mui/material';

export interface EyebrowProps {
  children: React.ReactNode;
  /** A heading element where the eyebrow names the block, not just labels it. */
  component?: 'div' | 'span' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  sx?: SxProps<Theme>;
}

/**
 * The small uppercase label above a block — a tag group's name, a flashcard's
 * two halves, a day in the capture feed. Every one goes through here so they
 * cannot drift into three letter-spacings and two sizes again.
 */
export const Eyebrow = ({ children, component = 'div', sx }: EyebrowProps) => (
  <Typography variant="eyebrow" component={component} sx={sx}>
    {children}
  </Typography>
);
