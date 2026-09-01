import { AppBarDrawer } from '@/components/layout/AppBarDrawer.tsx';
import { AppBarNavLinks } from '@/components/layout/AppBarNavLinks.tsx';
import { GlobalSearch } from '@/components/search/GlobalSearch.tsx';
import { AccountIcon, LogoutIcon, MenuIcon, SettingsIcon } from '@/theme/Icons.tsx';
import {
  Box,
  Container,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  AppBar as MuiAppBar,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { useAuth } from '../../context/AuthContext.tsx';

export function AppBar() {
  const { logout } = useAuth();
  const theme = useTheme();
  const isWide = useMediaQuery(theme.breakpoints.up('md'));
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [wasWide, setWasWide] = useState(isWide);
  if (isWide !== wasWide) {
    setWasWide(isWide);
    if (isWide) setIsDrawerOpen(false);
  }

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
  };

  return (
    <MuiAppBar
      position="sticky"
      elevation={2}
      sx={{
        backgroundColor: 'primary.main',
      }}
    >
      <Container maxWidth="xl" disableGutters>
        <Toolbar>
          {/* The same destinations the nav links carry, for a viewport with no
              room for them. */}
          <IconButton
            edge="start"
            aria-label="Open navigation"
            onClick={() => setIsDrawerOpen(true)}
            sx={{
              display: { xs: 'inline-flex', md: 'none' },
              mr: 1,
              color: 'primary.contrastText',
            }}
          >
            <MenuIcon />
          </IconButton>

          {/* Crossbill Icon and Title - Clickable */}
          <Box
            component={Link}
            to="/"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              textDecoration: 'none',
              color: 'inherit',
              '&:hover': {
                opacity: 0.9,
              },
            }}
          >
            <Box
              component="img"
              src="/icon-transparent.png"
              alt="Crossbill"
              sx={{
                height: 40,
                width: 40,
              }}
            />

            <Typography
              variant="h6"
              component="div"
              sx={{
                fontWeight: 700,
                color: 'primary.contrastText',
              }}
            >
              Crossbill
            </Typography>
          </Box>

          <AppBarNavLinks />

          {/* Spacer */}
          <Box sx={{ flexGrow: 1 }} />

          <GlobalSearch />

          <Box sx={{ flexGrow: { xs: 0, md: 1 } }} />

          {/* Account menu. Below `md` these entries are in the drawer, so the
              toolbar keeps to one row of controls. */}
          <IconButton
            color="inherit"
            aria-label="Account"
            onClick={handleMenuOpen}
            sx={{
              display: { xs: 'none', md: 'inline-flex' },
              color: 'primary.contrastText',
            }}
          >
            <AccountIcon />
          </IconButton>

          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
          >
            <MenuItem component={Link} to="/settings" onClick={handleMenuClose}>
              <ListItemIcon>
                <SettingsIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Settings</ListItemText>
            </MenuItem>
            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Log out</ListItemText>
            </MenuItem>
          </Menu>
        </Toolbar>
      </Container>

      <AppBarDrawer open={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} />
    </MuiAppBar>
  );
}
