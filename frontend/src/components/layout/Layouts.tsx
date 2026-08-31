import { Container, styled } from '@mui/material';

/**
 * PageContainer's horizontal gutters, in theme spacing units. Stated here
 * rather than left to MUI's Container defaults so anything that needs to line
 * up with the page's content column — a full-bleed carousel, say — can read the
 * same value instead of copying it.
 */
export const PAGE_GUTTER = { xs: 2, sm: 3 };

/**
 * What the sticky `AppBar` covers at the top of the viewport — MUI's `Toolbar`,
 * 56px below `sm` and 64px from there up. Anything scrolling a target to the
 * top of the page has to stop this far short of it, or the app bar lands on
 * top of what it just scrolled to.
 */
export const APP_BAR_HEIGHT = { xs: '56px', sm: '64px' };

/** The bottom navigation's own height, plus air, plus the device's safe area. */
export const BOTTOM_NAV_CLEARANCE = 'calc(56px + 24px + env(safe-area-inset-bottom))';

export const BOTTOM_NAV_CLEARANCE_VAR = '--bottom-nav-clearance';

/** MUI's snackbar offset below `lg`, plus a one-line `Alert`, plus air. */
export const SNACKBAR_CLEARANCE = 'calc(24px + 48px + 8px)';

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
