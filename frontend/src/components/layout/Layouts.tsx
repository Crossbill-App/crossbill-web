import { Container, styled } from '@mui/material';

/**
 * PageContainer's horizontal gutters, in theme spacing units. Stated here
 * rather than left to MUI's Container defaults so anything that needs to line
 * up with the page's content column — a full-bleed carousel, say — can read the
 * same value instead of copying it.
 */
export const PAGE_GUTTER = { xs: 2, sm: 3 };

/**
 * How far above the bottom edge floating chrome sits below `lg`, where the
 * book page's bottom navigation is fixed to it: the navigation's own height
 * plus the device's safe area, and 24px of air.
 */
export const BOTTOM_NAV_CLEARANCE = 'calc(80px + env(safe-area-inset-bottom))';

/**
 * The custom property the bottom navigation publishes while it is mounted,
 * holding `BOTTOM_NAV_CLEARANCE`. The snackbar reads it because its provider
 * sits above the router and cannot see which page is on screen; where the
 * property is unset — every page but the book page, and the book page on `lg`
 * — the snackbar keeps its own place at the bottom edge.
 */
export const BOTTOM_NAV_CLEARANCE_VAR = '--bottom-nav-clearance';

/**
 * How far chrome anchored to the bottom-right steps up to clear an open
 * snackbar: MUI puts the snackbar 24px off the bottom below `lg`, an `Alert`
 * is 48px tall on one line, and 8px keeps them apart.
 */
export const SNACKBAR_CLEARANCE = '80px';

export const PageContainer = styled(Container)(({ theme }) => ({
  paddingLeft: theme.spacing(PAGE_GUTTER.xs),
  paddingRight: theme.spacing(PAGE_GUTTER.xs),
  [theme.breakpoints.up('sm')]: {
    paddingLeft: theme.spacing(PAGE_GUTTER.sm),
    paddingRight: theme.spacing(PAGE_GUTTER.sm),
  },
  paddingBottom: `calc(${theme.spacing(18)} + env(safe-area-inset-bottom))`,
  [theme.breakpoints.up('xs')]: {
    marginTop: theme.spacing(3),
  },
  [theme.breakpoints.up('md')]: {
    marginTop: theme.spacing(4),
  },
  [theme.breakpoints.up('lg')]: {
    paddingBottom: theme.spacing(5),
  },
}));
