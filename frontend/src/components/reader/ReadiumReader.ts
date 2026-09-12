import {
  PublicationUnavailableError,
  type EbookLocation,
  type EbookReader,
  type EbookTocEntry,
  type OpenedEbook,
  type PageTurnDirection,
} from '@/components/reader/EbookReader.ts';
import { sanitizeResponse } from '@/components/reader/sanitizeResponse.ts';
import {
  EpubNavigator,
  type EpubNavigatorListeners,
  type IKeyboardPeripheralsConfig,
} from '@readium/navigator';
import { HttpFetcher, Locator, Manifest, Publication, type Link } from '@readium/shared';

const DESTROY_TIMEOUT_MS = 2000;

const CONTAINER_MARKER = 'data-ebook-reader';

// Readium appends its frames with no dimensions at all, so every one of them
// would render at the browser's default 300x150 box. Only the reflowable pool
// appends them to the container; the fixed-layout one positions its own wrappers.
const FRAME_STYLE = `[${CONTAINER_MARKER}] > .readium-navigator-iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: none;
}`;

/** ArrowRight and ArrowLeft, by the legacy key codes Readium's matcher compares. */
const PAGE_TURN_KEYS: IKeyboardPeripheralsConfig = [
  { type: 'next_page', keyCombos: [{ keyCode: 39, suppressOnInteractiveElement: true }] },
  { type: 'previous_page', keyCombos: [{ keyCode: 37, suppressOnInteractiveElement: true }] },
];

const toLocation = (locator: Locator): EbookLocation => ({
  href: locator.href,
  type: locator.type,
  title: locator.title,
  locations: {
    position: locator.locations.position,
    progression: locator.locations.progression,
    totalProgression: locator.locations.totalProgression,
    fragments: locator.locations.fragments,
  },
});

const fromLocation = (location: EbookLocation): Locator => {
  const locator = Locator.deserialize(location);
  if (!locator) throw new Error('That location does not name a place in a publication.');
  return locator;
};

const tocEntriesFrom = (links: Link[]): EbookTocEntry[] =>
  links.map((link) => ({
    href: link.href,
    title: link.title ?? '',
    children: tocEntriesFrom(link.children?.items ?? []),
  }));

const whenSized = (element: HTMLElement, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const isSized = () => element.clientWidth > 0 && element.clientHeight > 0;
    if (isSized()) {
      resolve();
      return;
    }
    if (signal.aborted) {
      reject(signal.reason as Error);
      return;
    }
    const observer = new ResizeObserver(() => {
      if (!isSized()) return;
      observer.disconnect();
      resolve();
    });
    // An element that never gains a size would leave the wait pending for as
    // long as the page lives.
    signal.addEventListener(
      'abort',
      () => {
        observer.disconnect();
        reject(signal.reason as Error);
      },
      { once: true }
    );
    observer.observe(element);
  });

/** The reader engine on `@readium/navigator`'s `EpubNavigator`. Single-use. */
export class ReadiumReader implements EbookReader {
  private readonly locationListeners = new Set<(location: EbookLocation) => void>();
  private readonly pageTurnListeners = new Set<(direction: PageTurnDirection) => void>();
  private readonly destruction = new AbortController();
  private navigator: EpubNavigator | undefined;
  private wrapper: HTMLDivElement | undefined;
  private isOpened = false;
  private isDestroyed = false;

  constructor(private readonly host: HTMLElement) {}

  async open(manifestUrl: string, signal?: AbortSignal): Promise<OpenedEbook> {
    signal?.throwIfAborted();
    if (this.isOpened) throw new Error('A reader opens one book; build another one.');
    this.isOpened = true;

    const publication = await this.publicationFrom(manifestUrl, signal);
    await this.checkpoint(signal);

    // A book with no position list is still readable; it just has no page numbers.
    const positions = await publication.positionsFromManifest().catch(() => []);
    await this.checkpoint(signal);

    // Readium sizes its frames from the container's parent and never recovers
    // from a 0x0 start.
    await whenSized(this.host, this.until(signal));
    await this.checkpoint(signal);

    const navigator = new EpubNavigator(
      this.mountContainer(),
      publication,
      this.navigatorListeners(),
      positions,
      undefined,
      { preferences: {}, defaults: {}, keyboardPeripherals: PAGE_TURN_KEYS }
    );
    this.navigator = navigator;

    await navigator.load();
    // The frame pool lays out from measurements that are final only once the
    // browser has painted the frames it just added.
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await navigator.resizeHandler();
    await this.checkpoint(signal);

    return {
      pageCount: positions.length,
      toc: tocEntriesFrom(publication.toc?.items ?? []),
      location: toLocation(navigator.currentLocator),
    };
  }

  async next(): Promise<void> {
    // At the last page Readium reports the same `false` it reports for a
    // location it cannot find, and running out of book is not a failure.
    await this.move((navigator, done) => navigator.goForward(true, done));
  }

  async previous(): Promise<void> {
    await this.move((navigator, done) => navigator.goBackward(true, done));
  }

  async goTo(location: EbookLocation): Promise<void> {
    const locator = fromLocation(location);
    const arrived = await this.move((navigator, done) => navigator.go(locator, false, done));
    if (!arrived) throw new Error('That location does not name a place in this book.');
  }

  onLocationChanged(listener: (location: EbookLocation) => void): () => void {
    return this.subscribe(this.locationListeners, listener);
  }

  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void {
    return this.subscribe(this.pageTurnListeners, listener);
  }

  async destroy(): Promise<void> {
    if (this.isDestroyed) return;
    this.isDestroyed = true;
    this.destruction.abort();

    const abandoned = this.navigator;
    this.navigator = undefined;
    if (abandoned) {
      // A destroy can hang for the same reason a load did; give it a moment,
      // then let it go.
      let timeout: ReturnType<typeof setTimeout> | undefined;
      await Promise.race([
        abandoned.destroy().catch(() => undefined),
        new Promise((resolve) => {
          timeout = setTimeout(resolve, DESTROY_TIMEOUT_MS);
        }),
      ]);
      clearTimeout(timeout);
    }
    this.wrapper?.remove();
    this.wrapper = undefined;
    this.locationListeners.clear();
    this.pageTurnListeners.clear();
  }

  /** The wrapper Readium's ResizeObserver may keep, and the container it draws into. */
  private mountContainer(): HTMLDivElement {
    // Readium's own ResizeObserver watches the container's parent for as long as
    // that parent lives, so the parent has to be ours to throw away.
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    wrapper.style.height = '100%';
    this.wrapper = wrapper;

    const container = document.createElement('div');
    container.setAttribute(CONTAINER_MARKER, '');
    container.style.position = 'relative';
    container.style.height = '100%';
    container.style.margin = '0 auto';
    const frameStyle = document.createElement('style');
    frameStyle.textContent = FRAME_STYLE;
    container.appendChild(frameStyle);
    wrapper.appendChild(container);
    this.host.appendChild(wrapper);

    return container;
  }

  private async publicationFrom(manifestUrl: string, signal?: AbortSignal): Promise<Publication> {
    const response = await fetch(manifestUrl, { signal });
    if (response.status === 404) throw new PublicationUnavailableError('missing');
    if (!response.ok) throw new PublicationUnavailableError('error');

    const manifest = await response
      .json()
      .then((payload: unknown) => Manifest.deserialize(payload))
      .catch(() => null);
    if (!manifest) throw new PublicationUnavailableError('error');

    // The self link is the publication's base URL, which Readium injects as
    // `<base href>` into every chapter, so the book's own relative URLs are ours.
    manifest.setSelfLink(manifestUrl);
    const fetchSanitized: typeof fetch = async (input, init) =>
      sanitizeResponse(await fetch(input, init));
    return new Publication({
      manifest,
      fetcher: new HttpFetcher(fetchSanitized, manifestUrl),
    });
  }

  private navigatorListeners(): EpubNavigatorListeners {
    return {
      frameLoaded: () => {},
      positionChanged: (locator) => this.notify(this.locationListeners, toLocation(locator)),
      timelineItemChanged: () => {},
      // Claimed so Readium's own quarter-screen pager does not turn pages
      // behind the UI's back.
      tap: () => true,
      click: () => true,
      zoom: () => {},
      miscPointer: () => {},
      scroll: () => {},
      customEvent: () => {},
      handleLocator: () => false,
      textSelected: () => {},
      contentProtection: () => {},
      contextMenu: () => {},
      peripheral: (event) => {
        if (event.type === 'next_page') this.notify(this.pageTurnListeners, 'next');
        if (event.type === 'previous_page') this.notify(this.pageTurnListeners, 'previous');
      },
    };
  }

  private move(
    command: (navigator: EpubNavigator, done: (ok: boolean) => void) => void
  ): Promise<boolean> {
    const navigator = this.navigator;
    // A reader with no book has nowhere to go, which is not the same answer as
    // a book without the place asked for.
    if (!navigator) return Promise.resolve(true);
    return new Promise((resolve) => command(navigator, resolve));
  }

  private subscribe<T>(listeners: Set<(value: T) => void>, listener: (value: T) => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  private notify<T>(listeners: Set<(value: T) => void>, value: T): void {
    for (const listener of [...listeners]) {
      try {
        listener(value);
      } catch {
        // A subscriber that throws must not reject Readium's in-flight navigation.
      }
    }
  }

  /** The caller's signal and this reader's own destruction, as one. */
  private until(signal?: AbortSignal): AbortSignal {
    if (!signal) return this.destruction.signal;
    return AbortSignal.any([signal, this.destruction.signal]);
  }

  private async checkpoint(signal?: AbortSignal): Promise<void> {
    if (!signal?.aborted && !this.isDestroyed) return;
    await this.destroy();
    throw signal?.reason ?? new DOMException('Aborted', 'AbortError');
  }
}
