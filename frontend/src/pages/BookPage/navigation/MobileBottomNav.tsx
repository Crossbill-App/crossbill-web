import { BOTTOM_NAV_CLEARANCE, BOTTOM_NAV_CLEARANCE_VAR } from '@/components/layout/Layouts.tsx';
import { MoreIcon } from '@/theme/Icons.tsx';
import {
  BottomNavigation,
  BottomNavigationAction,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Paper,
} from '@mui/material';
import { useNavigate, useParams, useRouterState } from '@tanstack/react-router';
import { useLayoutEffect, useState } from 'react';
import { BOOK_PAGE_LABELS, BOOK_PAGE_ROUTES } from './bookPageRoutes.ts';

const MORE_VALUE = 'more';

const PRIMARY_ROUTES = BOOK_PAGE_ROUTES.filter((route) => !route.overflow);
const OVERFLOW_ROUTES = BOOK_PAGE_ROUTES.filter((route) => route.overflow);

const getActivePage = (pathname: string): string => {
  const match = BOOK_PAGE_ROUTES.find((route) => pathname.includes(`/${route.segment}`));
  return match?.segment ?? 'structure';
};

export const MobileBottomNav = () => {
  const { bookId } = useParams({ strict: false });
  const { location } = useRouterState();
  const navigate = useNavigate();

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const menuOpen = Boolean(anchorEl);

  // The snackbar also anchors to the bottom edge, from a provider above the
  // router that cannot see this page. Publishing the room this navigation
  // takes lets it step aside here and sit at the edge everywhere else.
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.style.setProperty(BOTTOM_NAV_CLEARANCE_VAR, BOTTOM_NAV_CLEARANCE);
    return () => {
      root.style.removeProperty(BOTTOM_NAV_CLEARANCE_VAR);
    };
  }, []);

  const activePage = getActivePage(location.pathname);
  const isOverflowActive = OVERFLOW_ROUTES.some((route) => route.segment === activePage);
  // Highlight the "More" tab whenever the active destination lives in the menu.
  const bottomNavValue = isOverflowActive ? MORE_VALUE : activePage;

  const goToSegment = (segment: string) => {
    void navigate({
      to: `/book/$bookId/${segment}`,
      params: { bookId: bookId! },
      replace: true,
    });
  };

  const handleChange = (_event: React.SyntheticEvent, newValue: string) => {
    // The "More" tab opens the overflow menu (handled by its onClick) rather
    // than navigating anywhere itself.
    if (newValue === MORE_VALUE) return;
    goToSegment(newValue);
  };

  const handleOverflowSelect = (segment: string) => {
    setAnchorEl(null);
    goToSegment(segment);
  };

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1100,
        pb: 'env(safe-area-inset-bottom)',
      }}
    >
      <BottomNavigation value={bottomNavValue} onChange={handleChange} showLabels>
        {PRIMARY_ROUTES.map((route) => {
          const Icon = route.icon;
          return (
            <BottomNavigationAction
              key={route.segment}
              value={route.segment}
              label={BOOK_PAGE_LABELS[route.segment]}
              icon={<Icon />}
            />
          );
        })}
        <BottomNavigationAction
          value={MORE_VALUE}
          label="More"
          icon={<MoreIcon />}
          onClick={(event) => setAnchorEl(event.currentTarget)}
        />
      </BottomNavigation>
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {OVERFLOW_ROUTES.map((route) => {
          const Icon = route.icon;
          return (
            <MenuItem
              key={route.segment}
              selected={route.segment === activePage}
              onClick={() => handleOverflowSelect(route.segment)}
            >
              <ListItemIcon>
                <Icon fontSize="small" />
              </ListItemIcon>
              <ListItemText>{BOOK_PAGE_LABELS[route.segment]}</ListItemText>
            </MenuItem>
          );
        })}
      </Menu>
    </Paper>
  );
};
