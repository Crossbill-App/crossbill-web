import { PULL_THRESHOLD_PX, usePullToRefresh } from '@/hooks/usePullToRefresh';
import { useCacheEvents } from '@/lib/cacheEvents';
import { Box, CircularProgress } from '@mui/material';
import { type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

/** How far the content rests below its normal position while refreshing. */
const REFRESH_OFFSET_PX = 56;

/**
 * Wraps the app in a pull-down-to-refresh gesture that revalidates server
 * state, restoring on the iOS home-screen app what Safari's own chrome
 * provides in the browser.
 */
export function PullToRefresh({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { refreshRequested } = useCacheEvents();
  const { pullDistance, isRefreshing } = usePullToRefresh(refreshRequested);

  const offset = isRefreshing ? REFRESH_OFFSET_PX : pullDistance;

  return (
    <Box
      sx={{
        position: 'relative',
        transform: offset > 0 ? `translateY(${offset}px)` : 'none',
        transition: pullDistance > 0 ? 'none' : 'transform 0.2s ease-out',
      }}
    >
      {offset > 0 && (
        <Box
          sx={{
            position: 'absolute',
            top: -44,
            left: 0,
            right: 0,
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <CircularProgress
            size={28}
            aria-label={t('layout.pullToRefresh.refreshing')}
            variant={isRefreshing ? 'indeterminate' : 'determinate'}
            value={Math.min(pullDistance / PULL_THRESHOLD_PX, 1) * 100}
          />
        </Box>
      )}
      {children}
    </Box>
  );
}
