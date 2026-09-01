import { ArrowBackIcon } from '@/theme/Icons.tsx';
import { Button } from '@mui/material';
import { createLink } from '@tanstack/react-router';

const BackButton = createLink(Button);

/**
 * The way out of a book, for a viewport with no room for the app bar's nav
 * links. Reaching the library from here otherwise means opening the drawer
 * first, and leaving a book is the one navigation a reader makes from every
 * book page.
 *
 * Hidden from `md` up, where the bar's own Library link is already on screen a
 * few pixels above this one.
 */
export const BackToLibraryLink = () => (
  <BackButton
    to="/library"
    size="small"
    startIcon={<ArrowBackIcon />}
    sx={{
      display: { xs: 'inline-flex', md: 'none' },
      mb: 1,
      ml: -1,
      color: 'text.secondary',
    }}
  >
    Library
  </BackButton>
);
