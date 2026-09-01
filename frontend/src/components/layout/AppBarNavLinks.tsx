import { APP_ROUTES, isAppRouteActive } from '@/components/layout/appRoutes.ts';
import { alpha, Box, Button } from '@mui/material';
import { createLink, useLocation } from '@tanstack/react-router';

const NavButton = createLink(Button);

/**
 * The app's top-level destinations as a row of links in the app bar, for
 * viewports with room for them. Below `md` the same list is in the drawer.
 */
export const AppBarNavLinks = () => {
  const pathname = useLocation({ select: (location) => location.pathname });

  return (
    <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5, ml: 3 }}>
      {APP_ROUTES.map((route) => {
        const isActive = isAppRouteActive(route, pathname);

        return (
          <NavButton
            key={route.to}
            to={route.to}
            data-status={isActive ? 'active' : undefined}
            sx={{
              color: 'primary.contrastText',
              fontWeight: 400,
              // An underline rather than a filled pill: the bar is already a
              // solid colour, and a second block of colour on it reads as a
              // button to press rather than as where you are.
              borderBottom: 2,
              borderColor: 'transparent',
              borderRadius: 0,
              px: 1.5,
              '&:hover': {
                borderColor: (theme) => alpha(theme.palette.primary.contrastText, 0.4),
              },
              '&[data-status="active"], &[data-status="active"]:hover': {
                fontWeight: 600,
                borderColor: 'primary.contrastText',
              },
            }}
          >
            {route.label}
          </NavButton>
        );
      })}
    </Box>
  );
};
