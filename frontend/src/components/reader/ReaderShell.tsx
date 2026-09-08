import type { Highlight } from '@/api/generated/model';
import { isAnyDialogOpen } from '@/components/dialogs/dialogStack.ts';
import { CHROME_MARKER } from '@/components/reader/chromeMarker.ts';
import { HIGHLIGHT_DECORATION_GROUP } from '@/components/reader/decorations.ts';
import { ReaderChrome } from '@/components/reader/ReaderChrome.tsx';
import {
  readerPageColors,
  toEpubPreferences,
  type ReaderPreferences,
} from '@/components/reader/readerPreferences.ts';
import {
  loadReaderPreferences,
  saveReaderPreferences,
} from '@/components/reader/readerPreferenceStorage.ts';
import { TocDrawer } from '@/components/reader/TocDrawer.tsx';
import { useHighlightDecorations } from '@/components/reader/useHighlightDecorations.ts';
import { useReaderLanding, type ReaderLanding } from '@/components/reader/useReaderLanding.ts';
import { useReaderPublication } from '@/components/reader/useReaderPublication.ts';
import { useReaderSession } from '@/components/reader/useReaderSession.ts';
import { useReaderTapZones } from '@/components/reader/useReaderTapZones.ts';
import { useReadingPositionWriter } from '@/components/reader/useReadingPositionWriter.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { NextPageIcon, PreviousPageIcon } from '@/theme/Icons.tsx';
import { ICON_SIZE } from '@/theme/iconSizes.ts';
import {
  Box,
  Button,
  IconButton,
  Skeleton,
  Stack,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { EpubNavigator } from '@readium/navigator';
import type { Link, Locator, TimelineItem } from '@readium/shared';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Room in the margins for the page-turn buttons, so they never sit on the text.
 *
 * Only where those buttons are: on a phone the two gutters together were most of
 * the screen, and the book was reduced to a strip down the middle. Below the
 * breakpoint the buttons give way to tap zones and the reader keeps the width —
 * with no gutter of ours at all, because Readium's own page gutter already holds
 * the text 20px off each edge of the frame.
 */
const PAGE_TURN_GUTTER = 48;

/**
 * Air above and below the book, in theme spacing units.
 *
 * Readium's page gutter is horizontal only (`padding: 0 var(--RS__pageGutter)`),
 * so without this the first line sits against the chrome's border and the last
 * against the bottom of the screen. Nothing to double up with, at any width.
 */
const READING_SURFACE_INSET = 2;

/**
 * What the font-size control offers before there is a navigator to ask.
 *
 * Replaced by `EpubPreferencesEditor`'s own numbers as soon as one has loaded,
 * which is before the settings popover can be opened at all.
 */
const DEFAULT_FONT_SIZE_BOUNDS: { range: [number, number]; step: number } = {
  range: [0.7, 4],
  step: 0.05,
};

/**
 * How long a book gets to appear before the wait is called a failure.
 *
 * Only the frame-building phase is under this clock — the manifest and the
 * position list are separate queries that have already answered — so it covers
 * fetching a chapter or two and assembling their blobs. Generous for that, and
 * short enough that a reader who is never getting a book is told rather than
 * left watching a skeleton.
 *
 * Briefly 60s, while books would not open on iPhone Safari. That was a CSP
 * refusal rather than a slow load — `frame-ancestors 'none'`, inherited into
 * the reader's blob: frames and enforced there by WebKit alone — so the frame
 * failed instantly and no clock could have saved it. Waiting longer only meant
 * a minute of skeleton before the same apology.
 */
const BOOT_TIMEOUT_MS = 15_000;

/** How long an abandoned navigator gets to tear itself down before it is dropped. */
const DESTROY_TIMEOUT_MS = 2_000;

/**
 * How long the last leg of a jump gets before the book is shown where it is.
 *
 * `go` reports through a callback, and a callback is not a promise: it is
 * skipped outright while another navigation is in flight, and the search it
 * runs happens inside a frame this code cannot see into. The reader is already
 * in the right chapter by then, so the worst this bounds is a chapter head
 * instead of a passage — never a book that does not appear.
 */
const JUMP_TIMEOUT_MS = 3_000;

interface ReaderShellProps {
  bookId: number;
  title: string;
  onClose: () => void;
  /**
   * The book's highlights, for the colour their labels give each decoration —
   * and `undefined` until the book-details query has answered.
   *
   * Not the same as an empty array, which is a book nobody has marked. A
   * highlight is drawn before its label is known and skipped once the book is
   * known not to have it.
   */
  highlights: Highlight[] | undefined;
  /** Open the highlight a reader tapped on the page. */
  onOpenHighlight: (highlightId: number) => void;
  /**
   * The highlight `?highlightId=` named when this reader was opened, if any
   * (M3.3, #747) — the book opens *at* it and it is briefly emphasised.
   *
   * Read once, at mount, and latched below. The same param goes on to open the
   * highlight's dialog and is dropped again when that dialog is closed, and
   * neither of those is a reason to move the book: a reader who closes the
   * dialog is looking at the passage they came for.
   */
  highlightId?: number;
}

/** What the reader is told when a jump could not be made exactly (M3.4, #748). */
const MISSED_THE_HIGHLIGHT =
  "Couldn't find this highlight's exact place, so the book opened at the start of its chapter.";
const MISSED_THE_CHAPTER_TOO =
  "Couldn't find this highlight's place, so the book opened at the start.";
const LOST_THE_BOOKMARK = "Couldn't restore your last position, so the book opened at the start.";

/**
 * What to tell the reader about a book that did not open where it was asked to,
 * or `null` when there is nothing to say.
 *
 * `rejected` is the navigator having refused the landing outright and the boot
 * having started the book again from its beginning — so whatever was on offer,
 * the reader is at page one and is owed the same sentence as if it had never
 * been found. Which sentence that is depends on what was being asked for, which
 * is what `isJump` says.
 */
const apologyFor = (landing: ReaderLanding, rejected: boolean, isJump: boolean): string | null => {
  if (rejected) return isJump ? MISSED_THE_CHAPTER_TOO : LOST_THE_BOOKMARK;
  if (landing.missed === 'chapter') return MISSED_THE_HIGHLIGHT;
  if (landing.missed === 'start') return MISSED_THE_CHAPTER_TOO;
  if (landing.lost) return LOST_THE_BOOKMARK;
  return null;
};

/** Resolves once the element has a real box, or immediately if it already has one. */
const whenSized = (element: HTMLElement) =>
  new Promise<void>((resolve) => {
    if (element.clientWidth > 0 && element.clientHeight > 0) {
      resolve();
      return;
    }
    const observer = new ResizeObserver(() => {
      if (element.clientWidth > 0 && element.clientHeight > 0) {
        observer.disconnect();
        resolve();
      }
    });
    observer.observe(element);
  });

/**
 * The reader itself: one `EpubNavigator`, the chrome around it, and the two
 * credentials that let it read a book.
 *
 * Three things about the lifecycle are load-bearing.
 *
 * **The container is sized before the navigator sees it.** Readium gives its
 * iframes `position: absolute` and no dimensions at all, and sizes the
 * container from the *parent* it observes — so a navigator built against an
 * unsized element renders every frame at the browser's default 300x150 and
 * never recovers. The viewport below is a fixed, flex-sized element; the
 * navigator's own container is created inside it only once it measures
 * non-zero.
 *
 * **The navigator lives in a ref, never in state.** It is a mutable object
 * with a DOM subtree under it; putting it in state would re-render the tree
 * that owns that subtree on every page turn.
 *
 * **Boots are serialised.** React 19's StrictMode mounts effects twice, and
 * `destroy()` is asynchronous: without chaining, the first navigator's
 * teardown lands in the middle of the second one's load and takes its frames
 * with it.
 */
export const ReaderShell = ({
  bookId,
  title,
  onClose,
  highlights,
  onOpenHighlight,
  highlightId,
}: ReaderShellProps) => {
  const theme = useTheme();
  // A phone, near enough. The arrow buttons need gutters this viewport cannot
  // spare, so below here the edges of the page turn it instead.
  const isCompact = useMediaQuery(theme.breakpoints.down('sm'));
  const { showSnackbar } = useSnackbar();
  const { status: sessionStatus, isRenewing } = useReaderSession(bookId);
  const { status: publicationStatus, publication, positions } = useReaderPublication(bookId);
  // Where the book opens, and what it was: a place the reader left off at, or a
  // highlight they asked to be taken to. Latched at mount, so that the search
  // param going away with the highlight's dialog cannot move the book.
  const [target] = useState<number | null>(highlightId ?? null);
  const landing = useReaderLanding({
    bookId,
    target,
    positions,
    toc: publication?.toc?.items,
  });
  // Set when a book failed to open *at* the place it was given. The retry that
  // follows starts from the beginning, so the locator has to stop being offered.
  const [landingRejected, setLandingRejected] = useState(false);
  const openAt = landingRejected ? null : (landing?.locator ?? null);
  /**
   * Where the boot has to *finish* going once there are frames to go in, or
   * `null` where opening at the resource is the whole journey.
   *
   * Only a jump has one. A resume is resource-granular by M2.4's own design and
   * nothing here changes that; a jump promised the reader a passage.
   */
  const jumpTo = target !== null && landing?.missed === null && !landingRejected ? openAt : null;
  const { record: recordPosition, setArriving } = useReadingPositionWriter(bookId);

  const viewportRef = useRef<HTMLDivElement | null>(null);
  const navigatorRef = useRef<EpubNavigator | null>(null);
  const bootRef = useRef<Promise<unknown>>(Promise.resolve());

  const [isPageVisible, setIsPageVisible] = useState(false);
  const [locator, setLocator] = useState<Locator | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  /**
   * The contents entry the reader is currently in, or `null` where the book's
   * contents do not name it.
   *
   * Resolved by Readium's own `Timeline.tocEntryFor` rather than by matching
   * hrefs here. It answers in three tiers — the entry for this resource, then
   * the nearest preceding entry *within* the resource, then the nearest
   * preceding resource's entry — and the last two are worth more than a
   * hand-rolled match: the second marks the right section of a book published
   * as one long file, and the third marks a cover or an interstitial with the
   * chapter it follows rather than leaving the reader unplaced.
   */
  const [currentTocEntry, setCurrentTocEntry] = useState<Link | null>(null);
  /**
   * Whether the page is actually laid out in more than one column.
   *
   * Measured rather than inferred from the viewport, because the breakpoint is
   * the wrong question: Readium fits as many columns as the *optimal line
   * length* allows, so a 900px window, an iPad and any screen at all once the
   * font size is up are all single-column while being nowhere near a phone.
   * Read when the appearance popover opens, which is the moment the answer
   * matters and a moment when the layout has settled.
   */
  const [columnsArePossible, setColumnsArePossible] = useState(false);
  const [bootFailed, setBootFailed] = useState(false);
  // Bumped to ask for the whole navigator again, which is the only meaningful
  // retry: a half-built one has frames and blobs that have to go first.
  const [bootAttempt, setBootAttempt] = useState(0);
  // Seeded from the browser's own memory rather than from the defaults, and
  // read during the first render rather than in an effect: the navigator takes
  // its preferences at construction, and a font size that arrived a tick later
  // would mean every book visibly re-flowing the moment it opened.
  const [preferences, setPreferences] = useState<ReaderPreferences>(loadReaderPreferences);
  // Copied out of the navigator's own `EpubPreferencesEditor` once it exists,
  // rather than read off the instance while rendering: the editor is a live
  // object hanging off a ref, and a ref is not something a render may consult.
  const [fontSizeBounds, setFontSizeBounds] = useState(DEFAULT_FONT_SIZE_BOUNDS);

  // Stable, and reads the navigator out of the ref, so that wiring it into the
  // navigator's listeners is not a reason to rebuild the reader.
  const markTimelineItem = useCallback((item: TimelineItem | undefined) => {
    const navigator = navigatorRef.current;
    setCurrentTocEntry(
      navigator && item ? (navigator.timeline.tocEntryFor(item)?.link ?? null) : null
    );
  }, []);

  const measureColumns = useCallback(() => {
    const columns = navigatorRef.current?.settings.columnCount ?? null;
    setColumnsArePossible(columns !== null && columns > 1);
  }, []);

  const goForward = useCallback(() => navigatorRef.current?.goForward(true, () => {}), []);
  const goBackward = useCallback(() => navigatorRef.current?.goBackward(true, () => {}), []);

  // Spatial rather than logical, because a tap zone is a physical edge: in a
  // right-to-left book the next page is the one to the *left*. The navigator
  // resolves the two against the publication's reading progression.
  const goLeft = useCallback(() => navigatorRef.current?.goLeft(true, () => {}), []);
  const goRight = useCallback(() => navigatorRef.current?.goRight(true, () => {}), []);

  // The reader's own highlights, drawn on the page. Deliberately not part of
  // `isReady` below: the book opens without them and they land when they land.
  const {
    observer: decorationObserver,
    apply: applyDecorations,
    claimsPoint: decorationClaimsPoint,
  } = useHighlightDecorations({
    bookId,
    highlights,
    navigatorRef,
    onActivate: onOpenHighlight,
    // Nothing to emphasise where the reader did not arrive at the highlight:
    // a missed jump puts them at the start of a chapter, and a rejected landing
    // at the start of the book. Brightening a mark neither of them can see
    // would only be a mark that quietly changed colour later, somewhere else.
    emphasise: landing?.missed || landingRejected ? null : target,
    isPageVisible,
  });

  // What replaces the arrow buttons where there is no room for them. Stable for
  // the same reason `handleKeyDown` is, and bound to each frame in the same place.
  //
  // `isClaimed` is what keeps a tap on a highlight near the edge of a phone
  // screen from both opening the highlight and turning the page. Readium
  // reports an activation asynchronously, well after this listener has run, so
  // the zones ask the decoration layer directly instead of waiting to be told.
  const bindTapZones = useReaderTapZones({
    enabled: isCompact,
    suspended: isRenewing,
    onLeft: goLeft,
    onRight: goRight,
    isClaimed: decorationClaimsPoint,
  });

  // Mirrored into a ref so the key handler can consult it without becoming a
  // new function, which would mean rebinding every publication frame.
  const isRenewingRef = useRef(false);
  useEffect(() => {
    isRenewingRef.current = isRenewing;
  }, [isRenewing]);

  // Stable, because both page turns read the navigator out of a ref. That is
  // what lets the same handler be bound to each publication frame for its whole
  // life without the navigator having to be rebuilt.
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      if (isRenewingRef.current) return;
      // A dialog is over the book, and its arrows are its own — in the
      // highlight dialog they page between highlights. Both handlers listen on
      // the window, so the dialog calling `preventDefault` does not reach this
      // one, and a book turned underneath an open dialog stays turned once the
      // dialog closes. Asked of the shared stack rather than of a marker on one
      // dialog, so that a dialog added later is covered without being told to
      // mark itself.
      if (isAnyDialogOpen()) return;
      // An arrow key belongs to whatever control is using it. On the font-size
      // slider it is a font size, in the contents list it is the next chapter;
      // it is only a page turn when the book itself has the keyboard. Chrome
      // marks itself rather than being enumerated here, because the drawer and
      // the popover are portalled out of this tree and a DOM ancestor check is
      // the one test that still finds them. Events from inside a publication
      // frame arrive from another document, where this matches nothing.
      const target = event.target;
      if (target instanceof Element && target.closest(`[${CHROME_MARKER}]`)) return;
      // Somewhere text is being typed or edited, where an arrow moves a caret.
      // Not covered by the marker above: a field can be anywhere, including in
      // a surface that is nobody's idea of reader chrome.
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      )
        return;

      if (event.key === 'ArrowRight') goForward();
      else goBackward();
    },
    [goForward, goBackward]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // `landing` joins the other two for the same reason `positions` did: a
  // navigator takes its initial position once, at construction, so booting
  // before the answer is in can only be corrected by a visible jump after the
  // book has already rendered at the beginning. That is as true of a jump to a
  // highlight as it is of a resume, which is why both go through one answer.
  const isReady =
    sessionStatus === 'ready' &&
    publicationStatus === 'ready' &&
    !!publication &&
    positions !== undefined &&
    landing !== undefined;

  useEffect(() => {
    if (!isReady) return;
    const viewport = viewportRef.current;
    if (!viewport) return;

    // An AbortController rather than a plain flag: this boot is a chain of
    // awaits, and every step has to be able to ask whether it still matters.
    // Everything the navigator reports from here until the book has been laid
    // out is the book arriving, not the reader moving. Closed at the end of the
    // boot below, and re-opened by the cleanup so a retry starts held again.
    setArriving(true);

    const teardown = new AbortController();
    // Read through a call rather than the property: a narrowed flag is not what
    // this is, and the compiler would happily prove a later check redundant.
    const isStale = () => teardown.signal.aborted;
    // Disposal is tracked apart from staleness because the watchdog does both
    // at once and the cleanup that follows must not do the second one twice.
    const disposal = new AbortController();
    const isDisposed = () => disposal.signal.aborted;
    let epubNavigator: EpubNavigator | null = null;
    let container: HTMLDivElement | null = null;

    /**
     * Takes the navigator and its container down without waiting on the boot
     * that built them — which is the whole point, because the boot may be the
     * thing that is stuck.
     */
    const dispose = async () => {
      if (isDisposed()) return;
      disposal.abort();
      const abandoned = epubNavigator;
      const node = container;
      epubNavigator = null;
      container = null;
      if (navigatorRef.current === abandoned) navigatorRef.current = null;
      if (abandoned) {
        // A destroy can hang for the same reason a load did, and somebody is
        // waiting on a fresh reader: give it a moment, then let it go.
        await Promise.race([
          Promise.resolve()
            .then(() => abandoned.destroy())
            .catch(() => undefined),
          new Promise((resolve) => setTimeout(resolve, DESTROY_TIMEOUT_MS)),
        ]);
      }
      node?.remove();
    };

    const boot = bootRef.current.then(async () => {
      if (isStale()) return;
      await whenSized(viewport);
      if (isStale()) return;

      container = document.createElement('div');
      container.style.position = 'relative';
      container.style.height = '100%';
      container.style.margin = '0 auto';
      viewport.appendChild(container);

      epubNavigator = new EpubNavigator(
        container,
        publication,
        {
          /**
           * One frame of the publication is in the DOM and scriptable.
           *
           * It reveals the page and hands the frame the two ways of turning it
           * — the arrow keys and, where the buttons cannot fit, the tap zones —
           * neither of which a same-origin iframe bubbles up on its own.
           *
           * The decorations are re-offered here for one case only: a locator
           * list that answered while there was no navigator to hand it to. The
           * per-frame work is the navigator's own — it re-applies a resource's
           * decorations to a frame as that frame loads — so this is not where a
           * page turn gets its highlights, and it does not have to know which
           * resource this frame holds.
           */
          frameLoaded: (frameWindow: Window) => {
            frameWindow.addEventListener('keydown', handleKeyDown);
            bindTapZones(frameWindow);
            applyDecorations();
            setIsPageVisible(true);
          },
          /**
           * The navigator has settled somewhere new.
           *
           * Two readers of the same event: the chrome, which shows the page
           * number, and the position writer, which decides whether this is
           * worth telling the server about and keeps the reading session going
           * if it is.
           */
          positionChanged: (current: Locator) => {
            setLocator(current);
            recordPosition(current);
          },
          /**
           * The reader selected text in the book.
           *
           * `selection.locator` is populated by the navigator — the
           * browser-selection to Locator half of ADR-0004 §2's write path.
           * M4.1 converts it to an `XPointRange` and offers to highlight it;
           * until then, selecting text does what selecting text does.
           */
          textSelected: () => {},
          /**
           * The reader has moved into a different part of the book's own
           * timeline, which is what marks their place in the contents.
           */
          timelineItemChanged: markTimelineItem,
          // Readium pages the book itself on a pointer in the outer quarters of
          // a frame unless the listener claims the event. It has to stay
          // claimed: `useReaderTapZones` is what turns pages here, and a tap
          // answered twice would skip one.
          tap: () => true,
          click: () => true,
          zoom: () => {},
          miscPointer: () => {},
          scroll: () => {},
          customEvent: () => {},
          handleLocator: () => false,
          contentProtection: () => {},
          contextMenu: () => {},
          peripheral: () => {},
        },
        positions,
        // Where the reader left off, on this device or another. Handed to the
        // constructor rather than navigated to after `load()`: the frame pool
        // resolves it while building its first frame, so the book appears at
        // the right place instead of appearing at the beginning and then
        // jumping — and the navigator's first report is that place, which is
        // what keeps a restore from being written back as a move.
        openAt ?? undefined,
        { preferences: toEpubPreferences(theme, preferences), defaults: {} }
      );

      // Published before `load()`, because the two calls below reach the
      // navigator through this ref and the highlight layer has to be wired to
      // it before it has frames to wire into.
      navigatorRef.current = epubNavigator;
      // Registered with a real activation handler: the navigator turns
      // activation on for a group only when an observer that handles it
      // arrives, and every frame built from here is told the group is
      // activatable as it loads.
      epubNavigator.registerDecorationObserver(HIGHLIGHT_DECORATION_GROUP, decorationObserver);
      // Whatever has already been fetched, before the first frame exists. The
      // navigator holds the set and gives each frame its share as it loads.
      applyDecorations();

      await epubNavigator.load();
      // The frame pool is laid out from the container's measurements, which
      // are only final after the browser has painted the frames it just added.
      await new Promise((resolve) => requestAnimationFrame(resolve));
      await epubNavigator.resizeHandler();
      if (isStale()) return;
      const fontSize = epubNavigator.preferencesEditor.fontSize;
      setFontSizeBounds({ range: fontSize.supportedRange, step: fontSize.step });

      // The last leg of a jump, and it has to be its own call.
      //
      // A navigator resolves its *initial* position by resource alone:
      // `FramePoolManager.update` looks `locations.position` up in the position
      // list only to learn which href to build, and the progression, the
      // selector and the quoted text go no further. A book handed a highlight's
      // locator therefore opens at the top of its chapter — the right chapter,
      // the wrong place, and no way for the reader to tell the difference from
      // a jump that worked.
      //
      // `go` is what finishes it: it sends the quote and the selector into the
      // frame as `go_text` and lands on the words. So the constructor is still
      // given the locator — that is what keeps the book from appearing at page
      // one and then moving — and this walks the rest of the way before the
      // page is revealed. Inside the arriving bracket, so none of it is written
      // down as the reader going anywhere.
      if (jumpTo) {
        await Promise.race([
          new Promise<void>((resolve) => {
            epubNavigator?.go(jumpTo, false, () => resolve());
          }),
          new Promise((resolve) => setTimeout(resolve, JUMP_TIMEOUT_MS)),
        ]);
        if (isStale()) return;
      }
      setLocator(epubNavigator.currentLocator);
      // The navigator reports a timeline item only when it *changes*, so the
      // place the book opened at has to be asked for rather than waited for.
      markTimelineItem(epubNavigator.timeline.locate(epubNavigator.currentLocator));
      // The book is on screen and settled, so from here on a report is the
      // reader's own doing. Set synchronously rather than through state: the
      // settle report follows the layout by microtasks, and a render is not
      // something this can wait for.
      setArriving(false);
      clearTimeout(watchdog);
    });

    // A book that never arrives is indistinguishable, on screen, from one still
    // arriving: the skeleton looks the same either way. The watchdog is what
    // turns a load that has silently stopped — a hung fetch, a frame that never
    // fires — into something the reader can see and act on.
    const watchdog = setTimeout(() => {
      if (isStale()) return;
      setBootFailed(true);
      // The load is not coming back, and everything downstream of it is
      // chained to a promise that will never settle — the teardown, and so the
      // next attempt too. Abandon it here instead: the boot's remaining steps
      // become no-ops, the queue gets a fresh start so "Try again" is not
      // waiting behind the load that hung, and what was built comes down now
      // rather than whenever that load decides to finish.
      teardown.abort();
      bootRef.current = Promise.resolve();
      void dispose();
    }, BOOT_TIMEOUT_MS);

    boot.catch(() => {
      if (isStale()) return;
      // A book that would not open at the reader's place may still open at its
      // beginning: a stored locator is a reference into the EPUB as it was, and
      // the navigator refuses one that names a resource or a page this
      // publication no longer has. Losing a bookmark must not cost the book, so
      // the place is dropped and the boot tried again without it -- once, since
      // the second attempt is offering nothing that could be rejected.
      if (openAt) {
        setLandingRejected(true);
        setBootAttempt((attempt) => attempt + 1);
        return;
      }
      setBootFailed(true);
    });

    bootRef.current = boot.catch(() => undefined);

    return () => {
      teardown.abort();
      clearTimeout(watchdog);
      setArriving(true);
      setIsPageVisible(false);
      navigatorRef.current = null;
      // Already abandoned by the watchdog, which left a fresh promise in the
      // ref: chaining onto the hung boot again would put it straight back.
      if (isDisposed()) return;
      // Chained rather than immediate: destroying a navigator that is still
      // loading leaves its frames behind in the container. The `catch` comes
      // first so that teardown runs after a boot that *failed* too — chaining
      // it off `then` alone leaked a whole navigator, frames and blobs
      // included, every time a load went wrong and the reader tried again.
      bootRef.current = boot
        .catch(() => undefined)
        .then(dispose)
        .catch(() => undefined);
    };
    // `preferences` is deliberately absent: it seeds the navigator here and is
    // submitted to the live one below. Listing it would rebuild the reader,
    // and the book would jump back to page one on every font-size nudge.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isReady,
    publication,
    positions,
    openAt,
    jumpTo,
    theme,
    handleKeyDown,
    bindTapZones,
    recordPosition,
    setArriving,
    bootAttempt,
    // Both stable for the navigator's whole life, by construction: the
    // highlight layer reads the changing parts through refs precisely so that
    // a highlight being drawn is never a reason to rebuild the reader.
    decorationObserver,
    applyDecorations,
    markTimelineItem,
  ]);

  // Said once the book is on screen, so the reader reads it against the page it
  // is about rather than against a skeleton. Said once, and only where the book
  // is not where it was asked to be: a book nobody has read never had a place
  // to lose, and a highlight the reader landed on needs no explanation.
  //
  // Two apologies, because they are about different things (M3.4, #748). Losing
  // a bookmark is a thing that happened to the book; a jump that missed is
  // about the passage the reader just clicked on and is owed the more specific
  // sentence. Both are snackbars over the open book rather than anything to
  // dismiss: the reader came here to read, and the book is there to be read.
  const apologised = useRef(false);
  useEffect(() => {
    if (!isPageVisible || apologised.current || !landing) return;
    const message = apologyFor(landing, landingRejected, target !== null);
    if (!message) return;
    apologised.current = true;
    showSnackbar(message, 'info');
  }, [isPageVisible, landing, landingRejected, target, showSnackbar]);

  useEffect(() => {
    if (!isPageVisible) return;
    void navigatorRef.current?.submitPreferences(toEpubPreferences(theme, preferences));
  }, [isPageVisible, preferences, theme]);

  // Kept for the next book rather than for this one, so it is deliberately not
  // conditional on the navigator having taken them: a reader who nudges the
  // font size and closes the book has still expressed a preference.
  useEffect(() => {
    saveReaderPreferences(preferences);
  }, [preferences]);

  const goToTocEntry = useCallback((link: Link) => {
    setIsTocOpen(false);
    navigatorRef.current?.goLink(link, true, () => {});
  }, []);

  const pageColors = readerPageColors(theme, preferences.theme);
  const page = locator?.locations.position;
  const progression = locator?.locations.totalProgression;
  const pageCount = positions?.length ?? 0;
  const positionLabel =
    pageCount > 0 && page !== undefined
      ? `Page ${page} of ${pageCount}` +
        (progression === undefined ? '' : ` · ${Math.round(progression * 100)}%`)
      : null;

  if (publicationStatus === 'missing' || publicationStatus === 'error') {
    return (
      <ReaderMessage onClose={onClose}>
        {publicationStatus === 'missing'
          ? 'This book has no EPUB file, so there is nothing to read here yet. Upload one to read it in the browser.'
          : 'The book could not be opened. Please try again later.'}
      </ReaderMessage>
    );
  }

  if (sessionStatus === 'error') {
    return (
      <ReaderMessage onClose={onClose}>
        The reader could not start a session for this book. Please try again later.
      </ReaderMessage>
    );
  }

  if (bootFailed) {
    return (
      <ReaderMessage
        onClose={onClose}
        onRetry={() => {
          setBootFailed(false);
          setBootAttempt((attempt) => attempt + 1);
        }}
      >
        This book could not be opened in the reader.
      </ReaderMessage>
    );
  }

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: (t) => t.zIndex.appBar + 1,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: pageColors.background,
        color: pageColors.text,
        transition: (t) => t.transitions.create(['background-color', 'color']),
      }}
    >
      <ReaderChrome
        title={title}
        positionLabel={positionLabel}
        onOpenToc={() => setIsTocOpen(true)}
        onClose={onClose}
        preferences={preferences}
        onPreferencesChange={setPreferences}
        fontSizeRange={fontSizeBounds.range}
        fontSizeStep={fontSizeBounds.step}
        onOpenSettings={measureColumns}
        // Offered only where it would do something: where the page really is
        // in more than one column, or where the reader has already asked for
        // one and must be able to ask for the other again. A single-column
        // layout the reader never chose is Readium's answer to the width and
        // the font size, and a switch to force what is already true would be a
        // control that changed nothing.
        canChooseColumns={preferences.singleColumn || columnsArePossible}
      />

      <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
        {!isCompact && (
          <>
            <PageTurnButton edge="left" onClick={goBackward} disabled={isRenewing} />
            <PageTurnButton edge="right" onClick={goForward} disabled={isRenewing} />
          </>
        )}

        {/* The element the navigator measures. Its own container is created
            inside it once it has a box, and the frames Readium appends are
            given the dimensions the library does not set for itself. */}
        <Box
          ref={viewportRef}
          data-testid="reader-viewport"
          sx={{
            height: '100%',
            px: { xs: 0, sm: `${PAGE_TURN_GUTTER}px` },
            py: READING_SURFACE_INSET,
            visibility: isPageVisible ? 'visible' : 'hidden',
            '& .readium-navigator-iframe': {
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              border: 'none',
            },
          }}
        />

        {!isPageVisible && (
          <Stack
            aria-label="Loading the book"
            aria-busy="true"
            sx={{ position: 'absolute', inset: 0, p: 4, gap: 1.5, alignItems: 'center' }}
          >
            <Box sx={{ width: '100%', maxWidth: 640 }}>
              {Array.from({ length: 12 }, (_, index) => index).map((index) => (
                <Skeleton key={index} height={28} width={index % 5 === 4 ? '55%' : '100%'} />
              ))}
            </Box>
          </Stack>
        )}

        {/* The cookie behind every resource load has lapsed while the tab was
            away. Turning a page now would ask for a chapter with a dead
            credential and get a blank frame back, so the book is held — briefly,
            and over the page rather than instead of it — until the replacement
            lands. */}
        {isPageVisible && isRenewing && (
          <Stack
            aria-live="polite"
            sx={{
              position: 'absolute',
              inset: 0,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: pageColors.background,
              opacity: 0.9,
            }}
          >
            <Typography variant="body2">Reconnecting...</Typography>
          </Stack>
        )}
      </Box>

      <TocDrawer
        open={isTocOpen}
        onClose={() => setIsTocOpen(false)}
        toc={publication?.toc?.items ?? []}
        onSelect={goToTocEntry}
        current={currentTocEntry}
      />
    </Box>
  );
};

interface PageTurnButtonProps {
  edge: 'left' | 'right';
  onClick: () => void;
  disabled: boolean;
}

const PageTurnButton = ({ edge, onClick, disabled }: PageTurnButtonProps) => (
  <IconButton
    onClick={onClick}
    disabled={disabled}
    color="inherit"
    aria-label={edge === 'left' ? 'Previous page' : 'Next page'}
    sx={{
      position: 'absolute',
      top: '50%',
      transform: 'translateY(-50%)',
      [edge]: 4,
      zIndex: 1,
    }}
  >
    {edge === 'left' ? (
      <PreviousPageIcon sx={{ fontSize: ICON_SIZE.prominent }} />
    ) : (
      <NextPageIcon sx={{ fontSize: ICON_SIZE.prominent }} />
    )}
  </IconButton>
);

interface ReaderMessageProps {
  children: string;
  onClose: () => void;
  /** Offered only where trying again could plausibly work. */
  onRetry?: () => void;
}

/** The whole-viewport stand-in for a book that cannot be read. */
const ReaderMessage = ({ children, onClose, onRetry }: ReaderMessageProps) => (
  <Box
    sx={{
      position: 'fixed',
      inset: 0,
      zIndex: (t) => t.zIndex.appBar + 1,
      backgroundColor: 'background.default',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      p: 3,
    }}
  >
    <Stack spacing={3} sx={{ maxWidth: 480, alignItems: 'center', textAlign: 'center' }}>
      <Typography variant="body1" sx={{ color: 'text.secondary' }}>
        {children}
      </Typography>
      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onClose}>
          Back to book
        </Button>
        {onRetry && (
          <Button variant="contained" onClick={onRetry}>
            Try again
          </Button>
        )}
      </Stack>
    </Stack>
  </Box>
);
