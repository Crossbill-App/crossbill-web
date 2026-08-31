import { page } from 'vitest/browser';

/**
 * Runs `fn` with the browser resized to a phone, always restoring the config's
 * 1440×900 default afterward so a resize cannot leak into the next test.
 */
export const atCompactViewport = async (fn: () => Promise<void>) => {
  await page.viewport(400, 800);
  try {
    await fn();
  } finally {
    await page.viewport(1440, 900);
  }
};
