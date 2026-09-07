// SPIKE #740 — throwaway driver. Loads the spike reader route in headless
// Chromium, injects a token, and dumps console/network/DOM evidence.
//   node spike-740-drive.mjs <token> [bookId] [port]
import { chromium } from 'playwright';

const [, , token, bookId = '12', port = '5174'] = process.argv;
if (!token) throw new Error('usage: node spike-740-drive.mjs <token> [bookId] [port]');

const origin = `http://localhost:${port}`;
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

await page.addInitScript((t) => sessionStorage.setItem('spikeToken', t), token);

const console_ = [];
const failures = [];
const api = [];
page.on('console', (m) => console_.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => console_.push(`[pageerror] ${e.message}`));
page.on('requestfailed', (r) => failures.push(`${r.method()} ${r.url()} :: ${r.failure()?.errorText}`));
page.on('response', (r) => {
  if (r.url().includes('/api/v1/readium')) api.push(`${r.status()} ${r.url()}`);
});

await page.goto(`${origin}/spike/reader?bookId=${bookId}`, { waitUntil: 'load' });
await page.waitForTimeout(12000);

const probe = await page.evaluate(() => {
  const iframes = [...document.querySelectorAll('iframe')].map((f) => {
    let bodyText = null;
    let docTitle = null;
    try {
      bodyText = f.contentDocument?.body?.innerText?.slice(0, 300) ?? null;
      docTitle = f.contentDocument?.title ?? null;
    } catch (e) {
      bodyText = `CROSS-ORIGIN: ${e.message}`;
    }
    return { src: f.src.slice(0, 80), bodyText, docTitle };
  });
  return {
    iframeCount: iframes.length,
    iframes,
    readerHost: !!document.querySelector('[data-testid="spike-reader-host"]'),
    bodySnippet: document.body.innerText.slice(0, 400),
    // eslint-disable-next-line no-undef
    pub: window.__spike
      ? {
          isLoading: window.__spike.isLoading,
          profile: window.__spike.profile,
          selfLink: window.__spike.selfLink,
          isFXL: window.__spike.isFXL,
          error: window.__spike.error ? JSON.stringify(window.__spike.error) : null,
          readingOrder: window.__spike.publication?.readingOrder?.items?.length ?? null,
        }
      : null,
  };
});

await page.screenshot({ path: 'spike-740-reader.png', fullPage: false });

console.log('=== usePublication ===\n', JSON.stringify(probe.pub, null, 1));
console.log('=== DOM ===\n', JSON.stringify({ ...probe, pub: undefined }, null, 1));
console.log('=== api responses ===\n' + api.join('\n'));
console.log('=== request failures ===\n' + failures.join('\n'));
console.log('=== console ===\n' + console_.join('\n'));

await browser.close();
