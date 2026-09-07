import { chromium } from 'playwright';
const [, , token, port = '5174'] = process.argv;
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
await page.addInitScript((t) => sessionStorage.setItem('spikeToken', t), token);
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
await page.goto(`http://localhost:${port}/spike/bare?bookId=12`, { waitUntil: 'load' });
await page.waitForTimeout(12000);
console.log('status bar:', await page.locator('p').first().innerText().catch(() => 'n/a'));
for (let i = 0; i < 6; i++) { await page.getByRole('button', { name: 'Next' }).click(); await page.waitForTimeout(1800); }
await page.getByRole('button', { name: 'Highlight' }).click();
await page.waitForTimeout(2500);
const r = await page.evaluate(() => {
  const frames = [...document.querySelectorAll('[data-testid="bare-reader"] iframe')];
  return frames.map((f) => {
    const d = f.contentDocument;
    return {
      docTitle: d?.title ?? null,
      bodyText: d?.body?.innerText?.slice(0, 80) ?? null,
      highlightApiRanges: d?.defaultView?.CSS?.highlights ? d.defaultView.CSS.highlights.size : 'n/a',
      decorationStyles: d ? d.querySelectorAll('[id*="decoration"]').length : 0,
    };
  });
});
console.log('status bar after:', await page.locator('p').first().innerText().catch(() => 'n/a'));
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: 'spike-740-bare.png' });
console.log(logs.filter(l => l.includes('error') || l.includes('pageerror')).slice(0, 10).join('\n'));
await browser.close();
