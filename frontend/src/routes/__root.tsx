/* eslint-disable react-refresh/only-export-components */
import { AppBar } from '@/components/layout/AppBar';
import { PullToRefresh } from '@/components/layout/PullToRefresh';
import { Box, CircularProgress } from '@mui/material';
import { Navigate, Outlet, createRootRoute, useLocation } from '@tanstack/react-router';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { SettingsProvider, useSettings } from '../context/SettingsContext';

function AuthenticatedRoutes() {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const { settings, isLoading: isSettingsLoading } = useSettings();
  const location = useLocation();

  const isPublicPage = location.pathname === '/login' || location.pathname === '/register';

  // Show loading spinner while checking auth or loading settings
  if (isAuthLoading || isSettingsLoading) {
    return (
      <Box
        sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Redirect to login if trying to access registration when it's disabled
  if (location.pathname === '/register' && !settings?.feature_flags.user_registrations) {
    return <Navigate to="/login" />;
  }

  // Redirect to login if not authenticated (except on public pages)
  if (!isAuthenticated && !isPublicPage) {
    return <Navigate to="/login" />;
  }

  // Redirect to home if already authenticated and on public page
  if (isAuthenticated && isPublicPage) {
    return <Navigate to="/" />;
  }

  return (
    <PullToRefresh>
      {!isPublicPage && <AppBar />}
      <Outlet />
    </PullToRefresh>
  );
}

function RootComponent() {
  return (
    <SettingsProvider>
      <AuthProvider>
        <AuthenticatedRoutes />
      </AuthProvider>
    </SettingsProvider>
  );
}

export const Route = createRootRoute({
  component: RootComponent,
});
