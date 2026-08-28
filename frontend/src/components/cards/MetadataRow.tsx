import type { SxProps, Theme, TypographyProps } from '@mui/material';
import { Box, Typography } from '@mui/material';
import { Fragment, type ReactNode } from 'react';

interface MetadataRowProps {
  items: ReactNode[];
  variant?: TypographyProps['variant'];
  /** Keep the row on one line, ellipsising what does not fit. */
  noWrap?: boolean;
  sx?: SxProps<Theme>;
}

/**
 * The app's one metadata line: values joined by a middot, muted. Every row of
 * secondary facts — a highlight's date and page, a session's times, a book's
 * counts, a search hit's provenance — goes through here, so they cannot drift
 * into separate separators and weights again.
 */
export const MetadataRow = ({ items, variant = 'body2', noWrap, sx }: MetadataRowProps) => {
  const validItems = items.filter(
    (item) => item !== null && item !== undefined && item !== false && item !== ''
  );

  if (validItems.length === 0) {
    return null;
  }

  return (
    <Typography
      variant={variant}
      noWrap={noWrap}
      sx={[{ color: 'text.secondary' }, ...(Array.isArray(sx) ? sx : [sx])]}
    >
      {validItems.map((item, index) => (
        <Fragment key={index}>
          <span>{item}</span>
          {index < validItems.length - 1 && (
            <Box component="span" sx={{ color: 'text.disabled' }}>
              {'\u00a0·\u00a0'}
            </Box>
          )}
        </Fragment>
      ))}
    </Typography>
  );
};
