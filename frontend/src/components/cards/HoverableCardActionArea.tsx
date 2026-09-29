import { CardActionArea, styled } from '@mui/material';

/**
 * A list card that opens something: a highlight, a reading session's AI
 * summary, a search result. Hover is a background tint and a shadow lift, and
 * only where a pointer can actually hover.
 */
export const HoverableCardActionArea = styled(CardActionArea)(({ theme }) => ({
  borderRadius: theme.spacing(0.75),
  transition: 'all 0.2s ease',
  cursor: 'pointer',
  '@media (hover: hover)': {
    '&:hover': {
      backgroundColor: theme.palette.action.hover,
      boxShadow: theme.shadows[2],
    },
  },
}));
