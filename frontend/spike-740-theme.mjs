// SPIKE #740 — can thorium's chrome take our palette? It consumes 12
// --th-theme-* variables it never defines, so the host supplies them.
import { chromium } from 'playwright';
const [, , token, port = '5174'] = process.argv;
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
await page.addInitScript((t) => sessionStorage.setItem('spikeToken', t), token);
// Crossbill theme.ts: amber[700] primary, stone[50] page, stone[900] text.
await page.addStyleTag; // noop guard
await page.goto(`http://localhost:${port}/spike/reader?bookId=12`, { waitUntil: 'load' });
await page.waitForTimeout(10000);
await page.addStyleTag({
  content: `:root{
    --th-theme-background:#fafaf9;      /* stone[50]  */
    --th-theme-text:#1c1917;            /* stone[900] */
    --th-theme-subdue:#f5f5f4;
    --th-theme-subdue-text:#57534e;     /* stone[600] */
    --th-theme-select:#b45309;          /* amber[700] */
    --th-theme-onSelect:#ffffff;
    --th-theme-hover:rgba(104,90,75,0.08);
    --th-theme-onHover:#1c1917;
    --th-theme-focus:#b45309;
    --th-theme-disable:#a8a29e;
    --th-theme-elevate:#ffffff;
    --th-theme-immerse:#fafaf9;
  }`,
});
await page.waitForTimeout(1500);
console.log(JSON.stringify(await page.evaluate(() => {
  const b = getComputedStyle(document.body);
  return { bodyBg: b.backgroundColor, bodyColor: b.color };
}), null, 1));
await page.screenshot({ path: 'spike-740-themed.png' });
await browser.close();
