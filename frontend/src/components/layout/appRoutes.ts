import { HomeIcon, LibraryIcon } from '@/theme/Icons.tsx';
import type { SvgIconComponent } from '@mui/icons-material';

type AppRoute = '/' | '/library';

export interface AppRouteConfig {
  to: AppRoute;
  label: string;
  icon: SvgIconComponent;
  /** Paths that belong to this destination, including detail pages whose URL
   * is not nested below the destination itself. */
  activePathPrefixes: readonly string[];
}

/**
 * The app's top-level destinations, in the order they appear.
 *
 * Global navigation lives in the app bar rather than in a rail down the side:
 * the book page's left column is its own tab nav and its bottom bar is the
 * same nav on a phone, so a second column or a second bottom bar would be two
 * navigations competing for one edge. The bar sits above every page, which
 * makes it the one place a destination can be reached from anywhere.
 *
 * The desktop links and the mobile drawer both read this list, so a
 * destination cannot exist on one and not the other.
 */
export const APP_ROUTES: AppRouteConfig[] = [
  { to: '/', label: 'Home', icon: HomeIcon, activePathPrefixes: ['/'] },
  {
    to: '/library',
    label: 'Library',
    icon: LibraryIcon,
    activePathPrefixes: ['/library', '/book'],
  },
];

export const isAppRouteActive = (route: AppRouteConfig, pathname: string) =>
  route.activePathPrefixes.some((prefix) =>
    prefix === '/' ? pathname === prefix : pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
