import { chromium } from 'playwright';
const [, , token, port = '5174'] = process.argv;
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
await page.addInitScript((t) => sessionStorage.setItem('spikeToken', t), token);
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
await page.goto(`http://localhost:${port}/spike/reader?bookId=12`, { waitUntil: 'load' });
await page.waitForFunction(() => !!window.__seam?.nav, null, { timeout: 30000 });
await page.waitForTimeout(9000);
const r = await page.evaluate(() => {
  const nav = window.__seam.nav;
  return {
    currentLocator: nav.currentLocator() ? String(nav.currentLocator().href) : null,
    navLayout: String(nav.navLayout()),
    cframes: (nav.getCframes() ?? []).length,
    timeline: !!nav.timeline(),
    preferencesEditor: !!nav.preferencesEditor,
    domIframes: document.querySelectorAll('iframe').length,
  };
});
console.log(JSON.stringify(r, null, 1));
await browser.close();
