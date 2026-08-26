import { useEffect, useRef, useState } from 'react';

/** Pull distance, in pixels, that arms the refresh. */
export const PULL_THRESHOLD_PX = 70;

const MAX_PULL_PX = 120;
const RESISTANCE = 0.5;

/**
 * Pull-down-to-refresh gesture for the document scroller.
 *
 * iOS home-screen web apps have no browser chrome, so Safari's own
 * pull-to-refresh is unavailable there and the gesture has to be rebuilt from
 * touch events.
 */
export const usePullToRefresh = (onRefresh: () => Promise<unknown>) => {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const startYRef = useRef<number | null>(null);
  const pullRef = useRef(0);
  const refreshingRef = useRef(false);
  const onRefreshRef = useRef(onRefresh);

  useEffect(() => {
    onRefreshRef.current = onRefresh;
  });

  useEffect(() => {
    const setPull = (value: number) => {
      pullRef.current = value;
      setPullDistance(value);
    };

    const isAtTop = () => window.scrollY <= 0;

    const handleTouchStart = (event: TouchEvent) => {
      startYRef.current = event.touches.length === 1 && isAtTop() ? event.touches[0].clientY : null;
    };

    const handleTouchMove = (event: TouchEvent) => {
      if (startYRef.current === null || refreshingRef.current || !isAtTop()) return;

      const delta = event.touches[0].clientY - startYRef.current;
      if (delta <= 0) {
        // Pulled back up: release the gesture so the page scrolls normally.
        setPull(0);
        return;
      }

      // Only a non-passive listener may call this, which is why the listeners
      // are registered by hand instead of through React's touch props.
      event.preventDefault();
      setPull(Math.min(delta * RESISTANCE, MAX_PULL_PX));
    };

    const handleTouchEnd = () => {
      const shouldRefresh = pullRef.current >= PULL_THRESHOLD_PX;
      startYRef.current = null;
      setPull(0);
      if (!shouldRefresh) return;

      refreshingRef.current = true;
      setIsRefreshing(true);
      void onRefreshRef.current().finally(() => {
        refreshingRef.current = false;
        setIsRefreshing(false);
      });
    };

    const handleTouchCancel = () => {
      startYRef.current = null;
      setPull(0);
    };

    window.addEventListener('touchstart', handleTouchStart, { passive: true });
    window.addEventListener('touchmove', handleTouchMove, { passive: false });
    window.addEventListener('touchend', handleTouchEnd, { passive: true });
    window.addEventListener('touchcancel', handleTouchCancel, { passive: true });

    return () => {
      window.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleTouchEnd);
      window.removeEventListener('touchcancel', handleTouchCancel);
    };
  }, []);

  return { pullDistance, isRefreshing };
};
