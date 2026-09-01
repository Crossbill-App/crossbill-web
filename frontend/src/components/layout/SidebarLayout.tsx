import { Box } from '@mui/material';
import type { ReactNode } from 'react';

/** Width of either rail. Fixed, so the content column is the same measure on
 *  every page that uses this layout. */
const SIDEBAR_WIDTH = '280px';

interface SidebarLayoutProps {
  /** The navigation or filter rail. Its column is reserved whether or not the
   *  page fills it. */
  left: ReactNode;
  /** The right rail, for pages that have one. Reserved the same way when
   *  given, and left out of the grid entirely when not. */
  right?: ReactNode;
  children: ReactNode;
}

/**
 * The desktop reading layout: a fixed rail, a fixed content measure, and an
 * optional second rail.
 *
 * The columns are fixed rather than fluid because the book tabs used to own
 * their own layout, so the content column was one of three widths depending on
 * which tab you were looking at, and the page reflowed as you moved between
 * them. Callers decide when to render it — this is the wide-viewport layout,
 * and a page's narrow layout is its own business.
 */
export const SidebarLayout = ({ left, right, children }: SidebarLayoutProps) => (
  <Box
    sx={{
      display: 'grid',
      gridTemplateColumns:
        right === undefined ? `${SIDEBAR_WIDTH} 1fr` : `${SIDEBAR_WIDTH} 1fr ${SIDEBAR_WIDTH}`,
      gap: 4,
      alignItems: 'start',
    }}
  >
    <Box>{left}</Box>
    <Box component="main" sx={{ minWidth: 0 }}>
      {children}
    </Box>
    {right !== undefined && <Box>{right}</Box>}
  </Box>
);
