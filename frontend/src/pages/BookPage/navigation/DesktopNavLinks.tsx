import { Box, List, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';
import { createLink, useMatchRoute } from '@tanstack/react-router';
import { BOOK_PAGE_LABELS, BOOK_PAGE_ROUTES } from './bookPageRoutes.ts';

/**
 * The row *is* the link. Wrapping a `ListItemButton` in a `Link` gives every
 * nav item two nested tab stops — the anchor and the button inside it — so a
 * keyboard reader crosses each destination twice.
 *
 * `createLink` rather than `component={Link}`: `ListItemButton` copies `to`
 * into an `href` for anchor semantics, and TanStack Router's `Link` then
 * treats that injected `href` as authoritative and re-parses `search` off its
 * empty query string, dropping the real search params.
 */
const NavListItemButton = createLink(ListItemButton);

interface DesktopNavLinksProps {
  bookId: string;
}

export const DesktopNavLinks = ({ bookId }: DesktopNavLinksProps) => {
  const matchRoute = useMatchRoute();

  return (
    <Box sx={{ mb: 3 }}>
      <List disablePadding>
        {BOOK_PAGE_ROUTES.map((item) => {
          const isActive = !!matchRoute({ to: item.to, params: { bookId } });
          const Icon = item.icon;

          return (
            <NavListItemButton
              key={item.to}
              to={item.to}
              params={{ bookId }}
              selected={isActive}
              sx={{
                borderRadius: 1,
                mb: 0.5,
                py: 1,
                textDecoration: 'none',
                color: 'inherit',
                '&.Mui-selected': {
                  backgroundColor: 'action.selected',
                  '&:hover': {
                    backgroundColor: 'action.selected',
                  },
                },
              }}
            >
              <ListItemIcon
                sx={{ minWidth: 36, color: isActive ? 'primary.main' : 'text.secondary' }}
              >
                <Icon />
              </ListItemIcon>
              <ListItemText
                primary={BOOK_PAGE_LABELS[item.segment]}
                slotProps={{
                  primary: {
                    variant: 'body2',
                    sx: {
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? 'primary.main' : 'text.primary',
                    },
                  },
                }}
              />
            </NavListItemButton>
          );
        })}
      </List>
    </Box>
  );
};
