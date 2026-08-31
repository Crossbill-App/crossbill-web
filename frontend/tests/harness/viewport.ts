import { page } from 'vitest/browser';

/**
 * Runs `fn` with the browser resized to a phone, below `md` — where the book
 * page swaps its sidebars for a bottom nav and the app bar swaps its search
 * field for an icon. The config's 1440×900 default is always restored
 * afterward, even if `fn` throws, so a resize from one test can never leak
 * into the next.
 */
export const atCompactViewport = async (fn: () => Promise<void>) => {
  await page.viewport(400, 800);
  try {
    await fn();
  } finally {
    await page.viewport(1440, 900);
  }
};
