import { Container, styled } from '@mui/material';

/**
 * PageContainer's horizontal gutters, in theme spacing units. Stated here
 * rather than left to MUI's Container defaults so anything that needs to line
 * up with the page's content column — a full-bleed carousel, say — can read the
 * same value instead of copying it.
 */
export const PAGE_GUTTER = { xs: 2, sm: 3 };

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
