import { isAnyDialogOpen } from '@/components/dialogs/dialogStack.ts';
import {
  PublicationUnavailableError,
  type EbookAppearance,
  type EbookDecoration,
  type EbookLocation,
  type EbookReader,
  type EbookTocEntry,
  type OpenedEbook,
} from '@/components/reader/EbookReader.ts';
import { ReadiumReader } from '@/components/reader/ReadiumReader.ts';
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

/** How long a book has to appear before the reader is told it never will. */
const BOOT_TIMEOUT_MS = 15_000;

/** How an attempt at a book ended. */
type EbookReaderOutcome = 'open' | 'missing' | 'error' | 'timeout';

/** Whether the book is on screen, on its way there, or out of reach and why. */
type EbookReaderStatus = 'idle' | 'opening' | EbookReaderOutcome;

export interface UseEbookReaderOptions {
  host: RefObject<HTMLElement | null>;
  manifestUrl: string;
  /** False until the publication cookie exists; nothing is fetched before then. */
  enabled: boolean;
  /** True while a lapsed cookie is being replaced: a page fetched with a dead
   * credential comes back blank. */
  holdPageTurns: boolean;
  /** How the page should look; the book opens on it. */
  appearance: EbookAppearance;
  /** Where the book should open; `null` opens it at the beginning. */
  initialLocation?: EbookLocation | null;
  /** What to draw over the book; a new array is submitted to the engine, so keep it stable. */
  decorations: EbookDecoration[];
  /** Must be referentially stable: an inline arrow rebuilds the reader every render. */
  createReader?: (host: HTMLElement) => EbookReader;
  bootTimeoutMs?: number;
  /** Every place the book reports, `arriving` while it is still coming up. */
  onLocationReported?: (location: EbookLocation, arriving: boolean) => void;
  /** The id of a decoration the reader tapped. */
  onDecorationActivated?: (id: string) => void;
}

export interface EbookReaderState {
  status: EbookReaderStatus;
  pageCount: number;
  location: EbookLocation | null;
  toc: EbookTocEntry[];
  /** The contents entry covering where the reader is, or null where none does. */
  currentTocHref: string | null;
  /** Whether the book opened where it was asked to; null until one is on screen. */
  landedAt: OpenedEbook['landedAt'] | null;
  /** Null until a book is on screen: only an engine with one can report it. */
  fontSizeRange: [number, number] | null;
  next: () => void;
  previous: () => void;
  goTo: (location: EbookLocation) => void;
  retry: () => void;
}

const aReadiumReader = (host: HTMLElement): EbookReader => new ReadiumReader(host);

const outcomeOfFailure = (error: unknown): EbookReaderOutcome => {
  if (error instanceof PublicationUnavailableError) return error.reason;
  if (error instanceof DOMException && error.name === 'TimeoutError') return 'timeout';
  return 'error';
};

/** Whether the place the book was given could be what stopped it opening. */
const couldBeTheLanding = (error: unknown): boolean =>
  !(error instanceof PublicationUnavailableError) &&
  !(error instanceof DOMException && error.name === 'TimeoutError');

const NO_TOC: EbookTocEntry[] = [];

/** One book opened into a host element, and where the reader is in it. */
export const useEbookReader = ({
  host,
  manifestUrl,
  enabled,
  holdPageTurns,
  appearance,
  initialLocation,
  decorations,
  createReader = aReadiumReader,
  bootTimeoutMs = BOOT_TIMEOUT_MS,
  onLocationReported,
  onDecorationActivated,
}: UseEbookReaderOptions): EbookReaderState => {
  const [outcome, setOutcome] = useState<EbookReaderOutcome | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [location, setLocation] = useState<EbookLocation | null>(null);
  const [toc, setToc] = useState<EbookTocEntry[]>(NO_TOC);
  const [currentTocHref, setCurrentTocHref] = useState<string | null>(null);
  const [landedAt, setLandedAt] = useState<OpenedEbook['landedAt'] | null>(null);
  const [fontSizeRange, setFontSizeRange] = useState<[number, number] | null>(null);
  const [attempt, setAttempt] = useState(0);
  const readerRef = useRef<EbookReader | null>(null);
  // Through a ref, so a hold that starts mid-book never rebuilds the reader.
  const holdRef = useRef(holdPageTurns);
  useEffect(() => {
    holdRef.current = holdPageTurns;
  }, [holdPageTurns]);
  // The same, so that changing the appearance never rebuilds the reader; a
  // retry then opens on the current one rather than the one from mount.
  const appearanceRef = useRef(appearance);
  useEffect(() => {
    appearanceRef.current = appearance;
  }, [appearance]);
  const appliedRef = useRef<EbookAppearance | null>(null);
  // The same again, so a caller that rebinds its callback never rebuilds the reader.
  const reportedRef = useRef(onLocationReported);
  useEffect(() => {
    reportedRef.current = onLocationReported;
  }, [onLocationReported]);
  const activatedRef = useRef(onDecorationActivated);
  useEffect(() => {
    activatedRef.current = onDecorationActivated;
  }, [onDecorationActivated]);
  // And again, so that an answer arriving a second time cannot rebuild the
  // reader around it: where a book opens is settled when it opens. This effect
  // has to stay declared above the boot effect, which reads the ref on the very
  // render where `enabled` turns true — the initial value is still null then.
  const initialLocationRef = useRef(initialLocation);
  useEffect(() => {
    initialLocationRef.current = initialLocation;
  }, [initialLocation]);
  // A new set is drawn by the reader already on screen rather than a rebuilt one. Above
  // the boot effect, so a render that starts a boot hands the new reader the current set once.
  const decorationsRef = useRef(decorations);
  useEffect(() => {
    decorationsRef.current = decorations;
    readerRef.current?.applyDecorations(decorations);
  }, [decorations]);
  // Whether a place has already been refused once. Never reset: the second
  // attempt offers nothing that could be rejected, so a second failure is real.
  const refusedRef = useRef(false);

  useEffect(() => {
    const element = host.current;
    if (!enabled || !element) return;

    const reader = createReader(element);
    readerRef.current = reader;
    reader.applyDecorations(decorationsRef.current);
    // Read once per attempt: a retry after a refusal offers nothing.
    const offered = refusedRef.current ? null : initialLocationRef.current;
    const cancel = new AbortController();
    const signal = AbortSignal.any([cancel.signal, AbortSignal.timeout(bootTimeoutMs)]);
    let isOpen = false;
    const unsubscribes = [
      reader.onLocationChanged((location) => {
        setLocation(location);
        // Nothing a book reports before it has finished arriving is a move.
        reportedRef.current?.(location, !isOpen);
      }),
      reader.onTocEntryChanged(setCurrentTocHref),
      reader.onDecorationActivated((id) => activatedRef.current?.(id)),
      reader.onPageTurnRequested((direction) => {
        // Readium's pager sets a navigating flag it never clears when it has no
        // frames yet, so one key before the book is up kills every later turn.
        if (holdRef.current || !isOpen) return;
        // Readium steps aside only while focus is on what it counts as interactive, and a
        // dialog can drop focus to its own container, which it does not count.
        if (isAnyDialogOpen()) return;
        void (direction === 'next' ? reader.next() : reader.previous());
      }),
    ];

    const onOpened = (opened: OpenedEbook) => {
      if (cancel.signal.aborted) return;
      // The place the book settled on may never have been reported as a change,
      // so this is the only report a writer has to seed itself with.
      reportedRef.current?.(opened.location, true);
      isOpen = true;
      setPageCount(opened.pageCount);
      setLocation(opened.location);
      setToc(opened.toc);
      setCurrentTocHref(opened.tocHref);
      setFontSizeRange(opened.fontSizeRange);
      setLandedAt(opened.landedAt);
      setOutcome('open');
    };
    const onFailed = (error: unknown) => {
      // The one rejection that means nothing: this effect was cleaned up.
      if (cancel.signal.aborted) return;
      // A book that would not open at the reader's place may still open at its
      // beginning, and losing a bookmark must not cost them the book. Only for
      // a failure that could be the landing, though: the publication is fetched
      // and the watchdog armed before a landing is so much as looked at, so
      // retrying those would double the wait and blame the bookmark for it.
      if (offered && !refusedRef.current && couldBeTheLanding(error)) {
        refusedRef.current = true;
        setAttempt((count) => count + 1);
        return;
      }
      setOutcome(outcomeOfFailure(error));
    };

    // The engine cannot cancel a fetch Readium itself started, so a hanging
    // resource would leave `open` pending long past the watchdog's deadline.
    const abortedFirst = new Promise<never>((_, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason as Error), { once: true });
    });
    appliedRef.current = appearanceRef.current;
    const opening = reader.open(manifestUrl, {
      appearance: appearanceRef.current,
      initialLocation: offered ?? undefined,
      signal,
    });
    Promise.race([opening, abortedFirst]).then(onOpened, onFailed);

    return () => {
      cancel.abort();
      for (const unsubscribe of unsubscribes) unsubscribe();
      // Never awaited, and a reader is single-use, so the next run builds a
      // fresh one: that is what makes StrictMode's double mount harmless.
      void reader.destroy();
      readerRef.current = null;
    };
  }, [enabled, manifestUrl, attempt, createReader, bootTimeoutMs, host]);

  const next = useCallback(() => void readerRef.current?.next(), []);
  const previous = useCallback(() => void readerRef.current?.previous(), []);
  const goTo = useCallback(
    (destination: EbookLocation) => void readerRef.current?.goTo(destination),
    []
  );
  // Both, and in one go: the host is unmounted behind the message this is
  // offered on, and has to be back in the tree before the new attempt looks for it.
  const retry = useCallback(() => {
    setOutcome(null);
    // Nothing from the last attempt survives into the new one.
    setPageCount(0);
    setToc(NO_TOC);
    setCurrentTocHref(null);
    setFontSizeRange(null);
    setLandedAt(null);
    setAttempt((count) => count + 1);
  }, []);

  // Derived rather than stored, so that starting an attempt is not itself a
  // render: an effect that set the status would cascade one on every open.
  const status: EbookReaderStatus = enabled ? (outcome ?? 'opening') : 'idle';

  // Guarded, because nothing in the engine's own chain compares anything: an
  // appearance submitted again re-pushes CSS and reflows a book already right.
  useEffect(() => {
    if (status !== 'open' || appliedRef.current === appearance) return;
    appliedRef.current = appearance;
    void readerRef.current?.setAppearance(appearance);
  }, [appearance, status]);

  return {
    status,
    pageCount,
    location,
    toc,
    currentTocHref,
    landedAt,
    fontSizeRange,
    next,
    previous,
    goTo,
    retry,
  };
};
