import { Box, Typography } from '@mui/material';

export interface SectionTitleProps {
  children: React.ReactNode;
  component?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  /** The variant with the gradient rule running off to the right. */
  showDivider?: boolean;
  /** Off for headings whose own container owns the spacing. */
  gutterBottom?: boolean;
}

/**
 * The app's one section heading, in two variants: with the gradient rule and
 * without. Every heading at this rank goes through it — book content, the
 * sidebar, the chapter dialog, Settings — so they cannot drift into four
 * weights and two colours again.
 */
export const SectionTitle = ({
  children,
  component = 'h2',
  showDivider = false,
  gutterBottom = true,
}: SectionTitleProps) => {
  const heading = (
    <Typography
      variant="sectionTitle"
      component={component}
      gutterBottom={gutterBottom && !showDivider}
    >
      {children}
    </Typography>
  );

  if (!showDivider) {
    return heading;
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2.5, px: 0.5 }}>
      {heading}
      <Box
        sx={(theme) => ({
          height: '1px',
          flex: 1,
          background: `linear-gradient(to right, ${theme.palette.secondary.light}, transparent)`,
        })}
      />
    </Box>
  );
};
