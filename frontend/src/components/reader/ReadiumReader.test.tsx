import {
  PublicationUnavailableError,
  type EbookAppearance,
  type PageTurnDirection,
} from '@/components/reader/EbookReader.ts';
import { ReadiumReader } from '@/components/reader/ReadiumReader.ts';
import { fontSizeRangeConfig } from '@readium/navigator';
import { aManifest, aPositionList } from '@tests/fixtures/publication';
import { noPublication, readiumApi } from '@tests/msw/readiumApi';
import { worker } from '@tests/msw/worker';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

const MANIFEST_PATH = '/api/v1/readium/books/:bookId/manifest.json';
const MANIFEST_URL = `${window.location.origin}/api/v1/readium/books/1/manifest.json`;

/** The reader's defaults as the seam carries them: the light page, at the book's own size. */
const AN_APPEARANCE: EbookAppearance = {
  fontSize: 1,
  textAlign: null,
  columnCount: 1,
  pageBackgroundColor: '#fafaf9',
  pageTextColor: '#1c1917',
};

let host: HTMLDivElement;
let reader: ReadiumReader;

const recordEvents = () => {
  const positions: (number | undefined)[] = [];
  const turns: PageTurnDirection[] = [];
  const tocHrefs: (string | null)[] = [];
  reader.onLocationChanged((location) => positions.push(location.locations.position));
  reader.onPageTurnRequested((direction) => turns.push(direction));
  reader.onTocEntryChanged((href) => tocHrefs.push(href));
  return {
    positions,
    turns,
    tocHrefs,
    clear: () => {
      positions.length = 0;
      turns.length = 0;
      tocHrefs.length = 0;
    },
  };
};

/** The book on the reader's own defaults, which is what every test but the appearance ones needs. */
const openTheBook = (signal?: AbortSignal) =>
  reader.open(MANIFEST_URL, { appearance: AN_APPEARANCE, signal });

const frame = () => host.querySelector('iframe');

const frameText = () => frame()?.contentDocument?.body.textContent ?? '';

/** What ReadiumCSS has written into the chapter for one of its user settings. */
const userProperty = (name: string) =>
  frame()?.contentDocument?.documentElement.style.getPropertyValue(`--USER__${name}`) ?? '';

beforeEach(() => {
  host = document.createElement('div');
  host.style.width = '800px';
  host.style.height = '600px';
  document.body.appendChild(host);
  reader = new ReadiumReader(host);
});

afterEach(async () => {
  await reader.destroy();
  host.remove();
});

test('opens the book at its first page and names its chapters', async () => {
  worker.use(...readiumApi());

  const opened = await openTheBook();

  expect(opened.pageCount).toBe(2);
  expect(opened.location.locations.position).toBe(1);
  expect(opened.toc.map((entry) => entry.title)).toEqual(['On Attention', 'Part two']);
  expect(opened.toc[1].children.map((entry) => entry.title)).toEqual(['On Memory']);
  expect(frame()).not.toBeNull();
});

test("the book reports the font-size range the engine's own editor honours", async () => {
  worker.use(...readiumApi());

  const opened = await openTheBook();

  expect(opened.fontSizeRange).toEqual(fontSizeRangeConfig.range);
});

test('opening with an appearance paints it into the book', async () => {
  worker.use(...readiumApi());

  await reader.open(MANIFEST_URL, { appearance: AN_APPEARANCE });

  await expect.poll(() => userProperty('fontSize')).toBe('100%');
  expect(userProperty('backgroundColor')).toBe(AN_APPEARANCE.pageBackgroundColor);
  expect(userProperty('textColor')).toBe(AN_APPEARANCE.pageTextColor);
  // The book's own stylesheet is still the one setting lines.
  expect(userProperty('textAlign')).toBe('');
});

test('setAppearance reaches a book already on screen', async () => {
  worker.use(...readiumApi());
  await reader.open(MANIFEST_URL, { appearance: AN_APPEARANCE });
  await expect.poll(() => userProperty('fontSize')).toBe('100%');

  await reader.setAppearance({
    fontSize: 1.5,
    textAlign: 'justify',
    columnCount: null,
    pageBackgroundColor: '#1c1917',
    pageTextColor: '#f5f5f4',
  });

  await expect.poll(() => userProperty('textAlign')).toBe('justify');
  await expect.poll(() => userProperty('backgroundColor')).toBe('#1c1917');
  await expect.poll(() => userProperty('textColor')).toBe('#f5f5f4');
  await expect.poll(() => userProperty('fontSize')).toBe('150%');
});

test('next and previous turn the page and report where the reader is', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  const recorded = recordEvents();

  await reader.next();
  await expect.poll(() => recorded.positions).toContain(2);

  recorded.clear();
  await reader.previous();
  await expect.poll(() => recorded.positions).toContain(1);
});

test('the book names the contents entry it opened at', async () => {
  worker.use(...readiumApi());

  const opened = await openTheBook();

  expect(opened.tocHref).toBe('resources/OEBPS/chapter1.xhtml');
  expect(opened.toc[0].href).toBe('resources/OEBPS/chapter1.xhtml');
});

test('the reported contents entry follows the reader into the next chapter', async () => {
  worker.use(...readiumApi());
  const opened = await openTheBook();
  const recorded = recordEvents();
  const onMemory = opened.toc[1].children[0];

  await reader.next();

  await expect.poll(() => recorded.tocHrefs).toEqual([onMemory.href]);
});

test('a contents entry that declares no media type can be navigated to', async () => {
  worker.use(...readiumApi());
  const opened = await openTheBook();
  const recorded = recordEvents();
  const onMemory = opened.toc[1].children[0];
  expect(onMemory.type).toBe('');

  await reader.goTo({ href: onMemory.href, type: onMemory.type, locations: {} });

  await expect.poll(() => recorded.positions).toContain(2);
});

test('goTo lands on the location it is given', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  const recorded = recordEvents();

  await reader.goTo(aPositionList().positions[1]);

  await expect.poll(() => recorded.positions).toContain(2);
});

test('goTo rejects a location the book does not contain', async () => {
  worker.use(...readiumApi());
  await openTheBook();

  await expect(
    reader.goTo({
      href: 'resources/OEBPS/nowhere.xhtml',
      type: 'application/xhtml+xml',
      locations: {},
    })
  ).rejects.toThrow();
});

test('a manifest that claims another origin still has its chapters resolve against ours', async () => {
  worker.use(
    ...readiumApi({
      manifest: aManifest({
        links: [
          {
            href: 'https://elsewhere.example/api/v1/readium/books/1/manifest.json',
            rel: 'self',
            type: 'application/webpub+json',
          },
          {
            href: 'positions.json',
            rel: 'http://readium.org/position-list',
            type: 'application/vnd.readium.position-list+json',
          },
        ],
      }),
    })
  );

  await openTheBook();
  await expect.poll(frameText).toContain('On Attention');

  const base = frame()!.contentDocument!.querySelector('base')!.href;
  expect(base.startsWith(window.location.origin)).toBe(true);
});

test('the manifest and the resources are asked for without a bearer token', async () => {
  const requests: Request[] = [];
  worker.use(...readiumApi({ onRequest: (request) => requests.push(request) }));

  await openTheBook();

  const paths = requests.map((request) => new URL(request.url).pathname);
  expect(paths.some((path) => path.includes('/readium/books/1/resources/'))).toBe(true);
  expect(requests.filter((request) => request.headers.has('authorization'))).toEqual([]);
});

test('a book with no publication is reported as missing, an unreadable one as an error', async () => {
  worker.use(...noPublication);

  const missing = await openTheBook().catch((error: unknown) => error);

  expect(missing).toBeInstanceOf(PublicationUnavailableError);
  expect((missing as PublicationUnavailableError).reason).toBe('missing');
  expect(host.children).toHaveLength(0);

  worker.use(http.get(MANIFEST_PATH, () => new HttpResponse(null, { status: 500 })));
  const broken = new ReadiumReader(host);
  const failed = await broken
    .open(MANIFEST_URL, { appearance: AN_APPEARANCE })
    .catch((error: unknown) => error);

  expect(failed).toBeInstanceOf(PublicationUnavailableError);
  expect((failed as PublicationUnavailableError).reason).toBe('error');
  expect(host.children).toHaveLength(0);

  worker.use(http.get(MANIFEST_PATH, () => HttpResponse.html('<!doctype html>')));
  const notAManifest = new ReadiumReader(host);
  const garbled = await notAManifest
    .open(MANIFEST_URL, { appearance: AN_APPEARANCE })
    .catch((error: unknown) => error);

  expect(garbled).toBeInstanceOf(PublicationUnavailableError);
  expect((garbled as PublicationUnavailableError).reason).toBe('error');
  expect(host.children).toHaveLength(0);
});

test('an arrow key pressed inside the book asks for a page turn', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await expect.poll(frameText).toContain('On Attention');
  const recorded = recordEvents();

  frame()!.contentWindow!.focus();
  await userEvent.keyboard('{ArrowRight}');
  await expect.poll(() => recorded.turns).toEqual(['next']);

  await userEvent.keyboard('{ArrowLeft}');
  await expect.poll(() => recorded.turns).toEqual(['next', 'previous']);

  expect(recorded.positions).toEqual([]);

  recorded.clear();
  frame()!.blur();
  await userEvent.keyboard('{ArrowRight}');
  await expect.poll(() => recorded.turns).toEqual(['next']);
});

test('a book cannot run its own scripts against the page that opened it', async () => {
  worker.use(...readiumApi({ hostile: true }));

  // Unsanitised, the chapter's meta refresh navigates the frame away and the
  // open never settles; the assertions below are what has to report that.
  void openTheBook().catch(() => undefined);
  await expect.poll(frameText, { timeout: 5_000 }).toContain('On Attention');

  expect(document.body.getAttribute('data-pwned')).toBeNull();
  expect(frame()!.contentWindow!.location.href).toMatch(/^blob:/);
});

test('destroy removes the book from the page and can be called twice', async () => {
  worker.use(...readiumApi());
  await openTheBook();

  await reader.destroy();

  expect(frame()).toBeNull();
  expect(host.children).toHaveLength(0);
  await expect(reader.destroy()).resolves.toBeUndefined();
});

test('aborting an open leaves nothing behind', async () => {
  const controller = new AbortController();
  worker.use(
    ...readiumApi({
      onRequest: (request) => {
        if (request.url.includes('/resources/')) controller.abort();
      },
    })
  );

  await expect(openTheBook(controller.signal)).rejects.toThrow();

  expect(frame()).toBeNull();
  expect(host.children).toHaveLength(0);
});

test(
  'aborting while the host has no size settles instead of hanging',
  { timeout: 3_000 },
  async () => {
    worker.use(...readiumApi());
    host.style.width = '0';
    host.style.height = '0';
    const controller = new AbortController();

    const opening = openTheBook(controller.signal);
    setTimeout(() => controller.abort(), 100);

    await expect(opening).rejects.toThrow();
    expect(host.children).toHaveLength(0);
  }
);

test('destroying while the host has no size settles the open', { timeout: 3_000 }, async () => {
  worker.use(...readiumApi());
  host.style.width = '0';
  host.style.height = '0';

  const opening = openTheBook();
  setTimeout(() => void reader.destroy(), 100);

  await expect(opening).rejects.toThrow();
  expect(host.children).toHaveLength(0);
});
