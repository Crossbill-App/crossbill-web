import { APP_ROUTES } from '@/components/layout/appRoutes.ts';
import { useAuth } from '@/context/AuthContext.tsx';
import { LogoutIcon, SettingsIcon } from '@/theme/Icons.tsx';
import {
  Box,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import { createLink, useMatchRoute } from '@tanstack/react-router';

const NavListItemButton = createLink(ListItemButton);

const DRAWER_WIDTH = 260;

interface AppBarDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * The app's top-level destinations on a narrow viewport, plus the account
 * actions that sit behind the account icon on a wide one.
 *
 * A drawer rather than a bottom bar: the book page's bottom bar is already its
 * tab nav, and a second one would either cover it or fight it for the edge. A
 * drawer overlays whatever is underneath and leaves it alone.
 */
export const AppBarDrawer = ({ open, onClose }: AppBarDrawerProps) => {
  const { logout } = useAuth();
  const matchRoute = useMatchRoute();

  const handleLogout = () => {
    onClose();
    logout();
  };

  return (
    <Drawer anchor="left" open={open} onClose={onClose}>
      <Box sx={{ width: DRAWER_WIDTH }} role="presentation">
        <List>
          {APP_ROUTES.map((route) => {
            const isActive = !!matchRoute({ to: route.to, fuzzy: route.fuzzy });
            const Icon = route.icon;

            return (
              <NavListItemButton key={route.to} to={route.to} selected={isActive} onClick={onClose}>
                <ListItemIcon sx={{ color: isActive ? 'primary.main' : 'text.secondary' }}>
                  <Icon />
                </ListItemIcon>
                <ListItemText
                  primary={route.label}
                  slotProps={{
                    primary: {
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

        <Divider />

        <List>
          <NavListItemButton to="/settings" onClick={onClose}>
            <ListItemIcon sx={{ color: 'text.secondary' }}>
              <SettingsIcon />
            </ListItemIcon>
            <ListItemText primary="Settings" />
          </NavListItemButton>
          <ListItemButton onClick={handleLogout}>
            <ListItemIcon sx={{ color: 'text.secondary' }}>
              <LogoutIcon />
            </ListItemIcon>
            <ListItemText primary="Log out" />
          </ListItemButton>
        </List>
      </Box>
    </Drawer>
  );
};
