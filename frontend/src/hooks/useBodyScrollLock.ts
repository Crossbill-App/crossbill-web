import { lockBodyScroll, unlockBodyScroll } from '@/lib/bodyScrollLock.ts';
import { useEffect } from 'react';

/**
 * Pins the document scroller for as long as `locked` is true.
 *
 * Every overlay that covers the page needs this, MUI's own `overflow: hidden`
 * notwithstanding: iOS keeps scrolling the document by touch regardless, so
 * the page creeps behind the overlay and — with the page at the top — the
 * gesture is read as a pull-to-refresh instead of scrolling the overlay's own
 * content. The shared lock pins the body with `position: fixed`, which iOS
 * does honour, and `usePullToRefresh` sits the gesture out while it is held.
 */
export const useBodyScrollLock = (locked: boolean) => {
  useEffect(() => {
    if (!locked) return;

    lockBodyScroll();
    return unlockBodyScroll;
  }, [locked]);
};
