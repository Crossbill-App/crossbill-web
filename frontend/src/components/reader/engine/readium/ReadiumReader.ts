import {
  PublicationUnavailableError,
  type EbookAppearance,
  type EbookChapterProgress,
  type EbookDecoration,
  type EbookLocation,
  type EbookReader,
  type EbookSelection,
  type EbookTocEntry,
  type OpenEbookOptions,
  type OpenedEbook,
  type PageTurnDirection,
} from '@/components/reader/engine/EbookReader.ts';
import { listenerSet } from '@/components/reader/engine/listeners.ts';
import {
  chapterProgressAt,
  chapterStartsIn,
  resourceLayoutIn,
  sectionIdsIn,
} from '@/components/reader/engine/readium/chapterProgress.ts';
import {
  PAGE_TURN_KEYS,
  fromLocation,
  toDecoration,
  toEpubPreferences,
  toLocation,
  tocEntriesFrom,
} from '@/components/reader/engine/readium/conversions.ts';
import { landingFor } from '@/components/reader/engine/readium/landing.ts';
import { sanitizeResponse } from '@/components/reader/engine/readium/sanitizeResponse.ts';
import { type EbookResource } from '@/components/reader/engine/readium/selectionLocator.ts';
import { SelectionTracker } from '@/components/reader/engine/readium/SelectionTracker.ts';
import { EpubNavigator, type EpubNavigatorListeners } from '@readium/navigator';
import {
  HttpFetcher,
  Manifest,
  Publication,
  type Locator,
  type TimelineItem,
} from '@readium/shared';

const DESTROY_TIMEOUT_MS = 2000;

const CONTAINER_MARKER = 'data-ebook-reader';

// Readium keys decorations by group, replacing a whole group at a time and
// telling an observer only about its own, so the highlights own one name.
const DECORATION_GROUP = 'crossbill-highlights';

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
  private readonly locationListeners = listenerSet<EbookLocation>();
  private readonly pageTurnListeners = listenerSet<PageTurnDirection>();
  private readonly tocEntryListeners = listenerSet<string | null>();
  private readonly chapterProgressListeners = listenerSet<EbookChapterProgress | null>();
  private readonly decorationListeners = listenerSet<string>();
  private readonly destruction = new AbortController();
  /** Each resource of the publication by the URL its frame is built around. */
  private readonly resources = new Map<string, EbookResource>();
  private readonly selection: SelectionTracker;
  private decorations: EbookDecoration[] = [];
  private positions: Locator[] = [];
  private toc: EbookTocEntry[] = [];
  private chapterStarts: number[] = [];
  /** The window each resource was last loaded into, by its href. */
  private readonly frames = new Map<string, Window>();
  private navigator: EpubNavigator | undefined;
  private wrapper: HTMLDivElement | undefined;
  private isOpened = false;
  private isDestroyed = false;

  constructor(private readonly host: HTMLElement) {
    // In the body, not as a field initialiser: those run before the parameter
    // property is assigned, and the tracker is handed the host.
    this.selection = new SelectionTracker(host, (frame) =>
      this.resources.get(frame.document.baseURI)
    );
  }

  async open(
    manifestUrl: string,
    { appearance, initialLocation, signal }: OpenEbookOptions
  ): Promise<OpenedEbook> {
    signal?.throwIfAborted();
    if (this.isOpened) throw new Error('A reader opens one book; build another one.');
    this.isOpened = true;

    const publication = await this.publicationFrom(manifestUrl, signal);
    await this.checkpoint(signal);

    this.mapResources(publication);

    // A book with no position list is still readable; it just has no page numbers.
    const positions = await publication.positionsFromManifest().catch(() => []);
    await this.checkpoint(signal);
    const toc = tocEntriesFrom(publication.toc?.items ?? []);
    this.positions = positions;
    this.toc = toc;
    this.chapterStarts = chapterStartsIn(toc, positions);

    // Readium sizes its frames from the container's parent and never recovers
    // from a 0x0 start.
    await whenSized(this.host, this.until(signal));
    await this.checkpoint(signal);

    const landing = initialLocation ? landingFor(fromLocation(initialLocation), positions) : null;

    const navigator = new EpubNavigator(
      this.mountContainer(),
      publication,
      this.navigatorListeners(),
      positions,
      landing ?? undefined,
      {
        preferences: toEpubPreferences(appearance),
        defaults: {},
        keyboardPeripherals: PAGE_TURN_KEYS,
      }
    );
    this.navigator = navigator;
    // A group is activatable only for an observer that handles activation, so a
    // stub here would leave every decoration in the book inert.
    navigator.registerDecorationObserver(DECORATION_GROUP, {
      onDecorationActivated: ({ decoration }) => {
        this.decorationListeners.notify(decoration.id);
        return true;
      },
    });
    // Whatever was handed over before the navigator existed.
    this.applyDecorations(this.decorations);

    await navigator.load();
    // The frame pool lays out from measurements that are final only once the
    // browser has painted the frames it just added.
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await navigator.resizeHandler();
    await this.checkpoint(signal);

    return {
      pageCount: positions.length,
      toc,
      tocHref: this.tocEntryHrefFor(navigator.timeline.locate(navigator.currentLocator)),
      location: toLocation(navigator.currentLocator),
      chapterProgress: this.chapterProgressAt(navigator.currentLocator),
      landedAt: landing ? 'requested' : 'start',
      // Asked of the navigator's own editor rather than copied from the library's
      // `fontSizeRangeConfig`: a second copy of those numbers drifts on an upgrade.
      fontSizeRange: navigator.preferencesEditor.fontSize.supportedRange,
    };
  }

  async setAppearance(appearance: EbookAppearance): Promise<void> {
    await this.navigator?.submitPreferences(toEpubPreferences(appearance));
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

  applyDecorations(decorations: EbookDecoration[]): void {
    this.decorations = decorations;
    this.navigator?.applyDecorations(decorations.map(toDecoration), DECORATION_GROUP);
  }

  onDecorationActivated(listener: (id: string) => void): () => void {
    return this.decorationListeners.add(listener);
  }

  onSelectionChanged(listener: (selection: EbookSelection | null) => void): () => void {
    return this.selection.onChanged(listener);
  }

  clearSelection(): void {
    this.selection.clear();
  }

  startSelectionExtension(): void {
    this.selection.startExtension();
  }

  cancelSelectionExtension(): void {
    this.selection.cancelExtension();
  }

  onSelectionExtensionRefused(listener: () => void): () => void {
    return this.selection.onExtensionRefused(listener);
  }

  onLocationChanged(listener: (location: EbookLocation) => void): () => void {
    return this.locationListeners.add(listener);
  }

  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void {
    return this.pageTurnListeners.add(listener);
  }

  onTocEntryChanged(listener: (href: string | null) => void): () => void {
    return this.tocEntryListeners.add(listener);
  }

  onChapterProgressChanged(listener: (progress: EbookChapterProgress | null) => void): () => void {
    return this.chapterProgressListeners.add(listener);
  }

  async destroy(): Promise<void> {
    if (this.isDestroyed) return;
    this.isDestroyed = true;
    this.destruction.abort();

    const abandoned = this.navigator;
    this.navigator = undefined;
    if (abandoned) {
      // React has usually removed the host by now, and Readium hides a frame still
      // in a container by awaiting a reply the dead frame never sends: its observers
      // outlive it and its blobs are never revoked. A frame out of the page it just drops.
      this.wrapper?.querySelectorAll('iframe').forEach((frame) => frame.remove());
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
    this.selection.destroy();
    this.frames.clear();
    this.locationListeners.clear();
    this.pageTurnListeners.clear();
    this.tocEntryListeners.clear();
    this.chapterProgressListeners.clear();
    this.decorationListeners.clear();
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
    // A handle dragged past the edge of the book is let go of out here, where the
    // frame hears nothing: without this the press would never read as over.
    for (const type of ['pointerup', 'pointercancel'] as const) {
      this.host.ownerDocument.addEventListener(type, () => this.selection.pressEnded(), {
        capture: true,
        signal: this.destruction.signal,
      });
    }

    return container;
  }

  /**
   * Each reading-order resource under the URL its frame will be built around.
   *
   * Which resource a selection is in cannot be read off the frame it was made
   * in: the navigator loads every chapter from a blob URL, and the only thing
   * naming the original is the `<base href>` it writes into the document, which
   * is the resource's own URL. Asking the navigator where it currently is
   * instead would answer for the frame on screen rather than the one the
   * pointer went up in, and the two part company around a page turn.
   */
  private mapResources(publication: Publication): void {
    for (const link of publication.readingOrder.items) {
      const url = link.toURL(publication.baseURL);
      if (url) this.resources.set(url, { href: link.href, type: link.type ?? '' });
    }
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
      frameLoaded: (frame) => {
        this.selection.watch(frame);
        const resource = this.resources.get(frame.document.baseURI);
        if (resource) this.frames.set(resource.href, frame);
      },
      positionChanged: (locator) => {
        this.locationListeners.notify(toLocation(locator));
        this.chapterProgressListeners.notify(this.chapterProgressAt(locator));
      },
      timelineItemChanged: (item) => this.tocEntryListeners.notify(this.tocEntryHrefFor(item)),
      // Claimed so Readium's own quarter-screen pager does not turn pages
      // behind the UI's back.
      tap: () => true,
      click: () => true,
      zoom: () => {},
      miscPointer: () => {},
      scroll: () => {},
      customEvent: () => {},
      handleLocator: () => false,
      // Ignored in favour of the selection tracker: this one reports the words and a
      // rectangle, and says nothing about where in the book they are.
      textSelected: () => {},
      contentProtection: () => {},
      contextMenu: () => {},
      peripheral: (event) => {
        if (event.type === 'next_page') this.pageTurnListeners.notify('next');
        if (event.type === 'previous_page') this.pageTurnListeners.notify('previous');
      },
    };
  }

  /** Most places in a book have no contents entry of their own; `tocEntryFor`
   * walks back to the nearest one that covers them. */
  private tocEntryHrefFor(item: TimelineItem | undefined): string | null {
    const navigator = this.navigator;
    if (!navigator || !item) return null;
    return navigator.timeline.tocEntryFor(item)?.link.href ?? null;
  }

  /** Asked when the navigator reports a position, which it does once the page has settled. */
  private chapterProgressAt(locator: Locator): EbookChapterProgress | null {
    const frame = this.frames.get(locator.href);
    if (!frame) return null;
    const layout = resourceLayoutIn(frame, sectionIdsIn(this.toc, locator.href));
    return chapterProgressAt(locator, layout, this.chapterStarts, this.positions);
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
