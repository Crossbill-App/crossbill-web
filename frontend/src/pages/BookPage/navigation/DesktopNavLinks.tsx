import { Box, List, ListItemButton, ListItemIcon, ListItemText } from '@mui/material';
import { Link, useMatchRoute } from '@tanstack/react-router';
import { BOOK_PAGE_LABELS, BOOK_PAGE_ROUTES } from './bookPageRoutes.ts';

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
            <Link
              key={item.to}
              to={item.to}
              params={{ bookId }}
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <ListItemButton
                selected={isActive}
                sx={{
                  borderRadius: 1,
                  mb: 0.5,
                  py: 1,
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
              </ListItemButton>
            </Link>
          );
        })}
      </List>
    </Box>
  );
};
