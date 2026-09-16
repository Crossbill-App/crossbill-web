import {
  caretAt,
  rangeBetween,
  visibleRect,
  type CaretPoint,
} from '@/components/reader/caretRange.ts';
import {
  PublicationUnavailableError,
  type EbookAppearance,
  type EbookDecoration,
  type EbookLocation,
  type EbookReader,
  type EbookRect,
  type EbookSelection,
  type OpenEbookOptions,
  type OpenedEbook,
  type PageTurnDirection,
} from '@/components/reader/EbookReader.ts';
import { listenerSet } from '@/components/reader/listeners.ts';
import {
  PAGE_TURN_KEYS,
  fromLocation,
  toDecoration,
  toEpubPreferences,
  toLocation,
  tocEntriesFrom,
} from '@/components/reader/readiumConversions.ts';
import { landingFor } from '@/components/reader/readiumLanding.ts';
import { sanitizeResponse } from '@/components/reader/sanitizeResponse.ts';
import { selectionLocation, type EbookResource } from '@/components/reader/selectionLocator.ts';
import { EpubNavigator, type EpubNavigatorListeners } from '@readium/navigator';
import { HttpFetcher, Manifest, Publication, type TimelineItem } from '@readium/shared';
import { debounce } from 'lodash';

const DESTROY_TIMEOUT_MS = 2000;

/**
 * How long a changing selection is given to settle before it is reported.
 *
 * A drag fires `selectionchange` on every character it crosses, and a touch
 * handle keeps firing it for as long as a finger is on it.
 */
const SELECTION_SETTLE_MS = 200;

/** How far a finger may travel and still have meant a tap rather than a swipe. */
const TAP_SLOP_PX = 10;

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

/** Which event asked for a report: only the reader's own tap can let a held passage go. */
type ReportSource = 'tap' | 'settled';

/** A passage the engine is holding on to, with the point a further extension runs from. */
interface HeldPassage {
  selection: EbookSelection;
  start: CaretPoint;
}

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
  private readonly decorationListeners = listenerSet<string>();
  private readonly selectionListeners = listenerSet<EbookSelection | null>();
  private readonly extensionRefusedListeners = listenerSet<void>();
  private readonly destruction = new AbortController();
  /** Each resource of the publication by the URL its frame is built around. */
  private readonly resources = new Map<string, EbookResource>();
  private decorations: EbookDecoration[] = [];
  /** The last selection reported, as its own JSON, so the same one is not reported twice. */
  private reportedSelection: string | null = null;
  /** Where the selection being extended starts; `null` while none is being extended. */
  private extensionAnchor: CaretPoint | null = null;
  /** The passage an extension ended on, kept so that the browser alone cannot take it away. */
  private heldPassage: HeldPassage | null = null;
  private swallowNextClick = false;
  /** Whether a finger or button is still down on the book, mid-selection. */
  private isPressed = false;
  private navigator: EpubNavigator | undefined;
  private wrapper: HTMLDivElement | undefined;
  private isOpened = false;
  private isDestroyed = false;

  constructor(private readonly host: HTMLElement) {}

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
      toc: tocEntriesFrom(publication.toc?.items ?? []),
      tocHref: this.tocEntryHrefFor(navigator.timeline.locate(navigator.currentLocator)),
      location: toLocation(navigator.currentLocator),
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
    return this.selectionListeners.add(listener);
  }

  clearSelection(): void {
    for (const frame of this.host.querySelectorAll('iframe')) {
      frame.contentWindow?.getSelection()?.removeAllRanges();
    }
    this.heldPassage = null;
    // Now, not once `selectionchange` settles: the same words selected again
    // before then would be swallowed as a repeat.
    this.reportSelection(null);
  }

  startSelectionExtension(): void {
    for (const frame of this.host.querySelectorAll('iframe')) {
      const selection = frame.contentDocument?.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) continue;
      const { startContainer, startOffset } = selection.getRangeAt(0);
      selection.removeAllRanges();
      this.extendFrom({ node: startContainer, offset: startOffset });
      return;
    }
    // A browser showing nothing is not a reader who selected nothing: on iOS the
    // passage being held is the only record of where the words they see start.
    if (this.heldPassage) this.extendFrom(this.heldPassage.start);
  }

  cancelSelectionExtension(): void {
    this.extensionAnchor = null;
  }

  onSelectionExtensionRefused(listener: () => void): () => void {
    return this.extensionRefusedListeners.add(listener);
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
    this.extensionAnchor = null;
    this.heldPassage = null;
    this.extensionRefusedListeners.clear();
    this.locationListeners.clear();
    this.pageTurnListeners.clear();
    this.tocEntryListeners.clear();
    this.decorationListeners.clear();
    this.selectionListeners.clear();
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
      this.host.ownerDocument.addEventListener(type, () => (this.isPressed = false), {
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

  /** Reports what is selected in one frame of the book, whenever that changes. */
  private watchSelection(frame: Window): void {
    // A mouse is done the moment it is let go, and waiting out the settling
    // delay below to say so would leave the reader looking at selected words
    // and no way to act on them.
    frame.document.addEventListener('pointerdown', () => (this.isPressed = true), {
      capture: true,
    });
    for (const type of ['pointerup', 'pointercancel'] as const) {
      frame.document.addEventListener(type, () => (this.isPressed = false), { capture: true });
    }
    frame.document.addEventListener('pointerup', () => this.reportSelectionIn(frame, 'tap'));
    // Because the pointer going up is not the end of every selection: a touch
    // handle moves the range after it, and a keyboard selection never involves
    // a pointer at all. Not while the finger is still down, though: words offered
    // mid-drag cover the ones the reader is dragging towards.
    frame.document.addEventListener(
      'selectionchange',
      debounce(() => {
        if (!this.isPressed) this.reportSelectionIn(frame, 'settled');
      }, SELECTION_SETTLE_MS)
    );
  }

  /** What one frame of the book has selected, as the resource that frame is showing. */
  private selectionFound(frame: Window): EbookSelection | null {
    const resource = this.resources.get(frame.document.baseURI);
    return resource ? this.selectionIn(frame, resource) : null;
  }

  /** Reports what a frame has selected, which a passage being held outlives. */
  private reportSelectionIn(frame: Window, source: ReportSource): void {
    if (this.isDestroyed) return;
    const found = this.selectionFound(frame);
    // WebKit collapses a selection the engine made itself, which arrives here as
    // nothing being selected: a passage is let go of by a tap, never by the browser.
    if (!found && source === 'settled' && this.heldPassage) {
      this.reportSelection({ ...this.heldPassage.selection, shownAsSelected: false });
      return;
    }
    // A selection found while an extension waits is a swipe's doing, not the reader's:
    // the tap that ends the passage arrives through `watchExtension` instead.
    if (found && this.extensionAnchor) {
      frame.getSelection()?.removeAllRanges();
      return;
    }
    this.heldPassage = null;
    this.reportSelection(found);
  }

  /** Awaits the tap that ends a passage starting here, with nothing selected meanwhile. */
  private extendFrom(start: CaretPoint): void {
    this.extensionAnchor = start;
    this.heldPassage = null;
    // Let go now rather than on `selectionchange`: nothing may hold the reader's
    // gestures back while they are turning pages towards the end of the passage.
    this.reportSelection(null);
  }

  /** Makes the next tap in a frame the far end of the selection being extended. */
  private watchExtension(frame: Window): void {
    // Readium activates a decoration from a pointerup listener on this document, so a
    // tap the extension has taken has to be stopped here, before it travels on.
    const spend = (event: PointerEvent) => {
      this.swallowNextClick = true;
      event.stopPropagation();
    };
    let pressedAt: { x: number; y: number } | null = null;
    const extend = (event: PointerEvent) => {
      const anchor = this.extensionAnchor;
      if (!anchor) return;
      // A finger lifting after a swipe says where the page turn ended, not where the
      // passage does, and a swipe is how the reader reaches the page they want.
      const travelled =
        pressedAt && Math.hypot(event.clientX - pressedAt.x, event.clientY - pressedAt.y);
      if (travelled !== null && travelled > TAP_SLOP_PX) return;
      // Every tap while an extension waits is the extension's, wherever it lands.
      spend(event);
      if (frame.document !== anchor.node.ownerDocument) {
        // The anchor is kept: the reader can turn back to its chapter and tap again.
        this.extensionRefusedListeners.notify(undefined);
        return;
      }
      const caret = caretAt(frame.document, event.clientX, event.clientY);
      const range = caret && rangeBetween(anchor, caret);
      // Extend mode stays on: a tap picking no words is a miss, not a passage.
      if (!range || range.collapsed) return;
      const selection = frame.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      this.extensionAnchor = null;
      const passage = this.selectionFound(frame);
      // Held, because the words are shown as selected by a browser that need not keep
      // showing them: WebKit collapses a selection nobody dragged.
      this.heldPassage = passage && {
        selection: passage,
        start: { node: range.startContainer, offset: range.startOffset },
      };
      this.reportSelection(passage);
    };
    const swallow = (event: MouseEvent) => {
      if (!this.swallowNextClick) return;
      this.swallowNextClick = false;
      // That tap is spent on the extension: it must not also follow a link in the
      // book or reach anything else of the book's own that listens for a click.
      event.stopPropagation();
      event.preventDefault();
    };
    frame.document.addEventListener('pointerup', extend, { capture: true });
    frame.document.addEventListener('click', swallow, { capture: true });
    // A gesture beginning says the last one's click is never coming, and a swallow
    // left standing would eat this one instead.
    frame.document.addEventListener(
      'pointerdown',
      (event: PointerEvent) => {
        this.swallowNextClick = false;
        pressedAt = { x: event.clientX, y: event.clientY };
      },
      { capture: true }
    );
  }

  /** Keeps a touch gesture over selected words away from Readium's snapper. */
  private keepTouchFromTheSnapper(frame: Window): void {
    // The snapper listens on the frame's window in the bubble phase, so the document
    // hears first: its first move deselects, and its end reports a swipe.
    const holdsWords = () => {
      const selection = frame.getSelection();
      return !!selection && selection.rangeCount > 0 && !selection.isCollapsed;
    };
    let letThrough = false;
    const holdBack = (event: TouchEvent) => {
      // An extension waiting is the reader turning pages towards the end of the passage,
      // so nothing is held back: the selection a swipe leaves is dropped when reported.
      const hold = !this.extensionAnchor && holdsWords();
      // The snapper runs a state machine over the three events: one it has already begun
      // is stranded part-turned unless it hears an end.
      if (hold && letThrough) frame.dispatchEvent(new TouchEvent('touchend'));
      // Never `preventDefault`: the browser's own selection handles ride on the default.
      if (hold) event.stopPropagation();
      letThrough = !hold && event.type !== 'touchend' && event.type !== 'touchcancel';
    };
    for (const type of ['touchstart', 'touchmove', 'touchend', 'touchcancel'] as const) {
      frame.document.addEventListener(type, holdBack, { capture: true });
    }
  }

  /**
   * One report per passage.
   *
   * The two events above overlap by design — a mouse drag settles under both —
   * and every tap in the book ends with nothing selected, which is not news to
   * a reader who had selected nothing. Keyed on the location and on whether the
   * browser is showing it: a reflow that moves the same words is not a new
   * selection, while the browser dropping them is news the UI has to act on.
   */
  private reportSelection(selection: EbookSelection | null): void {
    const key = selection && JSON.stringify([selection.location, selection.shownAsSelected]);
    if (key === this.reportedSelection) return;
    this.reportedSelection = key;
    this.selectionListeners.notify(selection);
  }

  private selectionIn(frame: Window, resource: EbookResource): EbookSelection | null {
    const selected = frame.getSelection();
    if (!selected || selected.rangeCount === 0) return null;
    const range = selected.getRangeAt(0);
    const location = selectionLocation(range, resource);
    return location && { location, rect: this.onScreen(frame, range), shownAsSelected: true };
  }

  /** A range inside a frame, in the coordinates of the page the reader is on. */
  private onScreen(frame: Window, range: Range): EbookRect {
    const rect = visibleRect(frame, range);
    const origin = [...this.host.querySelectorAll('iframe')]
      .find((candidate) => candidate.contentWindow === frame)
      ?.getBoundingClientRect();
    return {
      x: rect.x + (origin?.x ?? 0),
      y: rect.y + (origin?.y ?? 0),
      width: rect.width,
      height: rect.height,
    };
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
        this.watchExtension(frame);
        this.watchSelection(frame);
        this.keepTouchFromTheSnapper(frame);
      },
      positionChanged: (locator) => this.locationListeners.notify(toLocation(locator)),
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
      // Ignored in favour of `watchSelection`: this one reports the words and a
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
