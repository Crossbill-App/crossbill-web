/**
 * Reference-counted body scroll lock, shared across every caller.
 *
 * Nested dialogs (a note opened on top of a highlight, say) each mount and
 * unmount their own lock effect; without a shared counter the inner dialog's
 * mount reads `window.scrollY` as 0 (the outer lock already made the body
 * `position: fixed`) and its unmount then clears the body styles the
 * still-open outer dialog needs. Only the first locker records the scroll
 * position and applies the styles; only the last unlocker restores them.
 */
let lockCount = 0;
let lockedScrollY = 0;

export const lockBodyScroll = () => {
  if (lockCount === 0) {
    lockedScrollY = window.scrollY;
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.top = `-${lockedScrollY}px`;
    document.body.style.width = '100%';
  }
  lockCount += 1;
};

export const unlockBodyScroll = () => {
  lockCount -= 1;
  if (lockCount === 0) {
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.width = '';
    window.scrollTo(0, lockedScrollY);
  }
};

/** Whether the document scroller is pinned, and `window.scrollY` therefore 0. */
export const isBodyScrollLocked = () => lockCount > 0;
