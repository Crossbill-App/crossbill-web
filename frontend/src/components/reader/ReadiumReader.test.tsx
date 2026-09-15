import {
  PublicationUnavailableError,
  type EbookAppearance,
  type EbookDecoration,
  type EbookLocation,
  type EbookSelection,
  type PageTurnDirection,
} from '@/components/reader/EbookReader.ts';
import { ReadiumReader } from '@/components/reader/ReadiumReader.ts';
import { fontSizeRangeConfig } from '@readium/navigator';
import { aDetailedPositionList, aManifest, aPositionList } from '@tests/fixtures/publication';
import { drawnOn, drawnRanges } from '@tests/harness/paintedHighlights';
import { rangeOver, select } from '@tests/harness/textSelection';
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
  lineHeight: null,
  paragraphSpacing: null,
  paragraphIndent: null,
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
  const selections: (EbookSelection | null)[] = [];
  reader.onLocationChanged((location) => positions.push(location.locations.position));
  reader.onPageTurnRequested((direction) => turns.push(direction));
  reader.onTocEntryChanged((href) => tocHrefs.push(href));
  reader.onSelectionChanged((selection) => selections.push(selection));
  return {
    positions,
    turns,
    tocHrefs,
    selections,
    clear: () => {
      positions.length = 0;
      turns.length = 0;
      tocHrefs.length = 0;
      selections.length = 0;
    },
  };
};

/** The book on the reader's own defaults, which is what every test but the appearance ones needs. */
const openTheBook = (signal?: AbortSignal) =>
  reader.open(MANIFEST_URL, { appearance: AN_APPEARANCE, signal });

/** The book opened at a place, the way a resume hands one over. */
const openTheBookAt = (initialLocation: EbookLocation) =>
  reader.open(MANIFEST_URL, { appearance: AN_APPEARANCE, initialLocation });

/** A place in the book's second chapter, which `aDetailedPositionList` splits in three. */
const inChapterTwo = (locations: EbookLocation['locations']): EbookLocation => ({
  href: 'resources/OEBPS/chapter2.xhtml',
  type: 'application/xhtml+xml',
  locations,
});

const CHAPTER_TWO = 'resources/OEBPS/chapter2.xhtml';

/** A highlight over a word the first chapter uses twice: in its heading, and in its text. */
const A_HIGHLIGHT: EbookDecoration = {
  id: 'highlight-7',
  location: {
    href: 'resources/OEBPS/chapter1.xhtml',
    type: 'application/xhtml+xml',
    locations: { cssSelector: 'p' },
    text: { highlight: 'Attention' },
  },
  tint: '#f59e0b',
  opacity: 0.35,
};

const frame = () => host.querySelector('iframe');

/** Where in the frame a reader would put their finger to hit that range. */
const centreOf = (range: Range) => {
  const rect = range.getClientRects()[0];
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
};

const frameText = () => frame()?.contentDocument?.body.textContent ?? '';

/** The chapter on screen: Readium keeps the neighbouring one loaded and hidden. */
const visibleFrame = () =>
  [...host.querySelectorAll('iframe')].find((candidate) => candidate.style.visibility !== 'hidden');

const visibleFrameText = () => visibleFrame()?.contentDocument?.body.textContent ?? '';

/** A selection changing under no pointer, the way a touch handle or a keyboard moves one. */
const adjustSelectionInBook = (phrase: string) => {
  const chapter = visibleFrame()!.contentDocument!;
  select(chapter, rangeOver(chapter, phrase));
};

/** A reader dragging over words in the chapter on screen, and letting go. */
const selectInBook = (phrase: string) => {
  adjustSelectionInBook(phrase);
  visibleFrame()!.contentDocument!.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
};

/** Longer than the engine gives a changing selection to settle. */
const afterTheSelectionSettles = () => new Promise((resolve) => setTimeout(resolve, 400));

/** The same gesture over nothing, which is what dropping a selection is. */
const tapTheBook = () => {
  const chapter = visibleFrame()!.contentDocument!;
  chapter.getSelection()?.removeAllRanges();
  chapter.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
};

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
  expect(opened.landedAt).toBe('start');
  expect(opened.toc.map((entry) => entry.title)).toEqual(['On Attention', 'Part two']);
  expect(opened.toc[1].children.map((entry) => entry.title)).toEqual(['On Memory']);
  expect(frame()).not.toBeNull();
});

test('a book opened at a stored position opens there', async () => {
  worker.use(...readiumApi());

  const opened = await openTheBookAt(aPositionList().positions[1]);

  expect(opened.landedAt).toBe('requested');
  expect(opened.location.locations.position).toBe(2);
  await expect.poll(visibleFrameText).toContain('On Memory');
});

test('a position number this publication does not have still opens at the right place', async () => {
  worker.use(...readiumApi({ positions: aDetailedPositionList() }));

  const opened = await openTheBookAt(
    inChapterTwo({ position: 99, progression: 0.5, totalProgression: 0.5 })
  );

  expect(opened.landedAt).toBe('requested');
  expect(opened.location.locations.position).toBe(3);
  await expect.poll(visibleFrameText).toContain('On Memory');
});

test('a locator carrying no position at all opens at its resource', async () => {
  worker.use(...readiumApi({ positions: aDetailedPositionList() }));

  const opened = await openTheBookAt(inChapterTwo({}));

  expect(opened.landedAt).toBe('requested');
  // The head of the resource: nothing in the locator says where inside it to go.
  expect(opened.location.locations.position).toBe(2);
  await expect.poll(visibleFrameText).toContain('On Memory');
});

test('a progression inside a split resource opens at the position covering it', async () => {
  worker.use(...readiumApi({ positions: aDetailedPositionList() }));

  const opened = await openTheBookAt(inChapterTwo({ progression: 0.5 }));

  expect(opened.landedAt).toBe('requested');
  // Not 2, which is where the resource begins.
  expect(opened.location.locations.position).toBe(3);
  // A position is a third of this chapter, so only the progression tells landing
  // part-way through it from landing at the top of the third that covers it.
  expect(opened.location.locations.progression).toBeGreaterThan(1 / 3);
});

test('a place in a resource this publication has not got opens the book at the start', async () => {
  worker.use(...readiumApi());

  const opened = await openTheBookAt({
    href: 'resources/OEBPS/nowhere.xhtml',
    type: 'application/xhtml+xml',
    locations: { position: 1, progression: 0 },
  });

  expect(opened.landedAt).toBe('start');
  expect(opened.location.locations.position).toBe(1);
  await expect.poll(visibleFrameText).toContain('On Attention');
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
  expect(userProperty('lineHeight')).toBe('');
});

test('setAppearance reaches a book already on screen', async () => {
  worker.use(...readiumApi());
  await reader.open(MANIFEST_URL, { appearance: AN_APPEARANCE });
  await expect.poll(() => userProperty('fontSize')).toBe('100%');

  await reader.setAppearance({
    fontSize: 1.5,
    lineHeight: 1.8,
    paragraphSpacing: 1,
    paragraphIndent: 1.5,
    textAlign: 'justify',
    columnCount: null,
    pageBackgroundColor: '#1c1917',
    pageTextColor: '#f5f5f4',
  });

  await expect.poll(() => userProperty('textAlign')).toBe('justify');
  await expect.poll(() => userProperty('lineHeight')).toBe('1.8');
  await expect.poll(() => userProperty('paraSpacing')).toBe('1rem');
  await expect.poll(() => userProperty('paraIndent')).toBe('1.5rem');
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

test('goTo with a quote lands on its words inside the element the selector names, not on their first occurrence', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  const progressions: (number | undefined)[] = [];
  reader.onLocationChanged((location) => progressions.push(location.locations.progression));

  await reader.goTo({
    ...inChapterTwo({ cssSelector: 'body > p:nth-of-type(200)' }),
    text: { highlight: 'rarest and purest' },
  });

  // The page holding paragraph 200 of 240 reports 0.89; the quote's first occurrence, 0.
  await expect.poll(() => progressions[progressions.length - 1]).toBeGreaterThan(0.5);
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

test('a decoration in a chapter the reader has not reached is drawn when they get there', async () => {
  worker.use(...readiumApi());

  reader.applyDecorations([
    { ...A_HIGHLIGHT, location: { ...A_HIGHLIGHT.location, href: CHAPTER_TWO } },
  ]);
  await openTheBook();
  await expect.poll(() => drawnOn(host)).toEqual([]);

  await reader.next();

  await expect.poll(() => drawnOn(host)).toEqual(['p:Attention']);
});

test('a decoration applied after the book is on screen is drawn too', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await expect.poll(frameText).toContain('On Attention');

  reader.applyDecorations([A_HIGHLIGHT]);

  await expect.poll(() => drawnOn(host)).toEqual(['p:Attention']);
});

test('tapping a decoration reports its id', async () => {
  worker.use(...readiumApi());
  const activated: string[] = [];
  reader.onDecorationActivated((id) => activated.push(id));
  reader.applyDecorations([A_HIGHLIGHT]);
  await openTheBook();
  await expect.poll(() => drawnOn(host)).toEqual(['p:Attention']);

  await userEvent.click(frame()!, { position: centreOf(drawnRanges(host)[0]) });

  await expect.poll(() => activated).toEqual([A_HIGHLIGHT.id]);
});

test('applying an empty set removes what was drawn', async () => {
  worker.use(...readiumApi());
  reader.applyDecorations([A_HIGHLIGHT]);
  await openTheBook();
  await expect.poll(() => drawnOn(host)).toEqual(['p:Attention']);

  reader.applyDecorations([]);

  await expect.poll(() => drawnRanges(host)).toEqual([]);
});

test('selecting words in the book reports where in the book they are', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await expect.poll(visibleFrameText).toContain('On Attention');
  const recorded = recordEvents();

  selectInBook('rarest and purest');

  await expect.poll(() => recorded.selections).toHaveLength(1);
  const selected = recorded.selections[0];
  expect(selected?.location.href).toBe('resources/OEBPS/chapter1.xhtml');
  expect(selected?.location.text?.highlight).toBe('rarest and purest');
  expect(selected?.location.text?.before).toContain('Attention is the ');
  // The words are in the chapter's only paragraph, and the selector reaches it.
  const selector = selected?.location.locations.cssSelector;
  expect(selector).toBe('body > p:nth-child(2)');
  expect(visibleFrame()!.contentDocument!.querySelector(selector ?? '')?.tagName).toBe('p');
  // Somewhere on the page, so a popover has something to sit beside.
  expect(selected?.rect.width).toBeGreaterThan(0);
  expect(selected?.rect.height).toBeGreaterThan(0);
});

test('a selection is reported against the chapter it was made in, not the one the book opened at', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await reader.next();
  await expect.poll(visibleFrameText).toContain('On Memory');
  const recorded = recordEvents();

  selectInBook('rarest and purest');

  await expect.poll(() => recorded.selections).toHaveLength(1);
  expect(recorded.selections[0]?.location.href).toBe(CHAPTER_TWO);
});

test('a selection dragged out after the pointer went up is reported at its new extent', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await expect.poll(visibleFrameText).toContain('On Attention');
  const recorded = recordEvents();
  selectInBook('rarest');
  await expect.poll(() => recorded.selections).toHaveLength(1);

  // What a touch handle does: the range grows with no pointer event to say so.
  adjustSelectionInBook('rarest and purest');

  await expect.poll(() => recorded.selections).toHaveLength(2);
  expect(recorded.selections[1]?.location.text?.highlight).toBe('rarest and purest');
});

test('the pointer going up and the selection settling report one passage between them', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await expect.poll(visibleFrameText).toContain('On Attention');
  const recorded = recordEvents();

  selectInBook('rarest and purest');
  await afterTheSelectionSettles();

  expect(recorded.selections).toHaveLength(1);
});

test('letting a selection go is reported once, and tapping on is not reported at all', async () => {
  worker.use(...readiumApi());
  await openTheBook();
  await expect.poll(visibleFrameText).toContain('On Attention');
  const recorded = recordEvents();
  selectInBook('generosity');
  await expect.poll(() => recorded.selections).toHaveLength(1);

  tapTheBook();
  await expect.poll(() => recorded.selections).toHaveLength(2);
  expect(recorded.selections[1]).toBeNull();

  tapTheBook();
  tapTheBook();
  expect(recorded.selections).toHaveLength(2);
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
