import { APP_ROUTES } from '@/components/layout/appRoutes.ts';
import { Box, Button } from '@mui/material';
import { createLink, useMatchRoute } from '@tanstack/react-router';

const NavButton = createLink(Button);

/**
 * The app's top-level destinations as a row of links in the app bar, for
 * viewports with room for them. Below `md` the same list is in the drawer.
 */
export const AppBarNavLinks = () => {
  const matchRoute = useMatchRoute();

  return (
    <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5, ml: 3 }}>
      {APP_ROUTES.map((route) => {
        const isActive = !!matchRoute({ to: route.to, fuzzy: route.fuzzy });

        return (
          <NavButton
            key={route.to}
            to={route.to}
            sx={{
              color: 'primary.contrastText',
              fontWeight: isActive ? 600 : 400,
              // An underline rather than a filled pill: the bar is already a
              // solid colour, and a second block of colour on it reads as a
              // button to press rather than as where you are.
              borderBottom: 2,
              borderColor: isActive ? 'primary.contrastText' : 'transparent',
              borderRadius: 0,
              px: 1.5,
              '&:hover': { borderColor: isActive ? 'primary.contrastText' : 'currentColor' },
            }}
          >
            {route.label}
          </NavButton>
        );
      })}
    </Box>
  );
};
