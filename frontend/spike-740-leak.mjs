import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
await page.goto('http://localhost:5174/login', { waitUntil: 'load' });
await page.waitForTimeout(4000);
console.log(JSON.stringify(await page.evaluate(() => {
  const b = getComputedStyle(document.body);
  const btn = document.querySelector('button');
  return {
    route: location.pathname,
    bodyOverflow: b.overflow,
    bodyHeight: b.height,
    bodyTouchAction: b.touchAction,
    firstButtonAppearance: btn ? getComputedStyle(btn).webkitAppearance : 'no button',
    thoriumStylesheetPresent: [...document.styleSheets].some((s) => {
      try { return [...s.cssRules].some((r) => r.cssText.includes('thorium_web')); } catch { return false; }
    }),
  };
}, null), null, 1));
await browser.close();
