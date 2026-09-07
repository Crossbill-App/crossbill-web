// SPIKE #740 — throwaway. Answers the load-bearing question: from inside a
// thorium-web tree, can OUR code apply a highlight decoration?
//   node spike-740-seam.mjs <token> [bookId] [port]
import { chromium } from 'playwright';

const [, , token, bookId = '12', port = '5174'] = process.argv;
const origin = `http://localhost:${port}`;

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
await page.addInitScript((t) => sessionStorage.setItem('spikeToken', t), token);

const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));

await page.goto(`${origin}/spike/reader?bookId=${bookId}`, { waitUntil: 'load' });
await page.waitForFunction(() => !!window.__seam?.nav, null, { timeout: 30000 });
await page.waitForTimeout(6000);

// --- 1. What is actually reachable from public thorium API? -----------------
const surface = await page.evaluate(() => {
  const s = window.__seam;
  const nav = s.nav;
  const cframes = nav.getCframes?.() ?? [];
  const fm = cframes.find(Boolean);
  return {
    useEpubNavigatorKeys: s.keys,
    hasApplyDecorations: typeof nav.applyDecorations,
    hasRegisterDecorationObserver: typeof nav.registerDecorationObserver,
    // useNavigator().unified.underlying is documented as `VisualNavigator`;
    // check whether that is the EpubNavigator instance or the hook wrapper.
    frameManagerKeys: fm ? Object.getOwnPropertyNames(Object.getPrototypeOf(fm)) : null,
    frameManagerHasMsg: fm ? typeof fm.msg : null,
    frameCommsHasSend: fm?.msg ? typeof fm.msg.send : null,
    frameCommsReady: fm?.msg ? fm.msg.ready : null,
    cframeCount: cframes.length,
  };
});

// --- 2. Navigate to a chapter with prose, then try to decorate it ----------
const jumped = await page.evaluate(() => {
  const nav = window.__seam.nav;
  const pub = window.__spike.publication;
  const link =
    pub.readingOrder.items.find((i) => i.href.includes('chapter-1')) ??
    pub.readingOrder.items.find((i) => i.href.includes('introduction'));
  if (!link) return { error: 'no prose chapter found' };
  window.__link = link;
  nav.goLink(link, false, () => {});
  return { href: link.href };
});
await page.waitForTimeout(6000);

const decorated = await page.evaluate(() => {
  const s = window.__seam;
  const nav = s.nav;
  const { Locator, LocatorLocations, LocatorText, resolveDecorationForWire, DecorationStyleType } = s;
  const link = window.__link;

  // Grab a real phrase out of the rendered frame so the text-quote anchor hits.
  const fm = (nav.getCframes() ?? []).find((f) => f && f.source && f.window?.document?.body);
  if (!fm) return { error: 'no frame manager' };
  const p = fm.window.document.querySelector('p');
  const phrase = p?.textContent?.trim().split(/\s+/).slice(0, 8).join(' ');
  if (!phrase) return { error: 'no prose in frame' };

  const locator = new Locator({
    href: link.href,
    type: 'application/xhtml+xml',
    locations: new LocatorLocations({ otherLocations: new Map() }),
    text: new LocatorText({ highlight: phrase }),
  });

  const decoration = {
    id: 'spike-740-1',
    locator,
    style: { type: DecorationStyleType.Highlight, tint: '#ffd54f' },
  };

  // THE ATTEMPT: push a decoration straight down FrameManager.msg (FrameComms),
  // which is the wire the navigator's own applyDecorations uses.
  const wire = resolveDecorationForWire(decoration, undefined);
  fm.msg.send('decorate', { group: 'crossbill-highlights', action: 'add', decoration: wire });
  window.__fm = fm;
  return { chapter: link.href, phrase, wireKeys: Object.keys(wire), sent: true };
});
await page.waitForTimeout(3000);

const painted = await page.evaluate(() => {
  const fm = window.__fm;
  if (!fm) return { error: 'no frame' };
  const doc = fm.window.document;
  const els = doc.querySelectorAll(
    '[data-decoration-id], .readium-decoration, [class*="decorat"], [id*="decorat"]'
  );
  return {
    paintedCount: els.length,
    paintedSample: [...els].slice(0, 3).map((e) => e.outerHTML.slice(0, 220)),
    highlightApiRanges: doc.defaultView.CSS?.highlights ? doc.defaultView.CSS.highlights.size : 'n/a',
  };
});

console.log('=== reachable surface ===\n', JSON.stringify(surface, null, 1));
console.log('=== jump ===\n', JSON.stringify(jumped, null, 1));
console.log('=== decoration attempt ===\n', JSON.stringify(decorated, null, 1));
console.log('=== painted ===\n', JSON.stringify(painted, null, 1));
await page.screenshot({ path: 'spike-740-decoration.png' });
console.log('=== console tail ===\n' + logs.slice(-25).join('\n'));

await browser.close();
