import {
  PublicationUnavailableError,
  type EbookAppearance,
  type EbookChapterProgress,
  type EbookDecoration,
  type EbookLocation,
  type EbookReader,
  type EbookSelection,
  type EbookTocEntry,
  type OpenedEbook,
} from '@/components/reader/engine/EbookReader.ts';
import { ReadiumReader } from '@/components/reader/engine/readium/ReadiumReader.ts';
import { useCallback, useEffect, useEffectEvent, useRef, useState, type RefObject } from 'react';

/** How long a book has to appear before the reader is told it never will. */
const BOOT_TIMEOUT_MS = 15_000;

/** How long finishing a landing may hold the page back before the book is shown where it opened. */
const FINISH_LANDING_TIMEOUT_MS = 3_000;

/** How an attempt at a book ended. */
type EbookReaderOutcome = 'open' | 'missing' | 'error' | 'timeout';

/** Whether the book is on screen, on its way there, or out of reach and why. */
type EbookReaderStatus = 'idle' | 'opening' | EbookReaderOutcome;

/** What a book on screen reports, as one group of listeners. */
interface EbookReaderListeners {
  /** Every place the book reports while it is still coming up; the last one is where it opened. */
  arrivedAt?: (location: EbookLocation) => void;
  /** A place the book reports once it is on screen. */
  movedTo?: (location: EbookLocation) => void;
  /** The id of a decoration the reader tapped. */
  decorationActivated?: (id: string) => void;
  /** A tap that could not extend the selection, the remembered start still standing. */
  selectionExtensionRefused?: () => void;
}

export interface UseEbookReaderOptions {
  host: RefObject<HTMLElement | null>;
  manifestUrl: string;
  /** False until the publication cookie exists; nothing is fetched before then. */
  enabled: boolean;
  /** Asked on every page-turn request the engine reports, at that moment; the
   * turn happens only when it answers true. */
  canTurnPage: () => boolean;
  /** How the page should look; the book opens on it. */
  appearance: EbookAppearance;
  /** Where the book should open; `null` opens it at the beginning. */
  initialLocation?: EbookLocation | null;
  /** Must be referentially stable: an inline arrow rebuilds the reader every render. */
  createReader?: (host: HTMLElement) => EbookReader;
  /** Who to tell about what the reader does with the book. */
  on?: EbookReaderListeners;
  /** Where to move the book once it has opened, before it is shown; `null` shows it where it opened. */
  finishLanding?: (opened: OpenedEbook) => EbookLocation | null;
}

export interface EbookReaderState {
  status: EbookReaderStatus;
  pageCount: number;
  location: EbookLocation | null;
  toc: EbookTocEntry[];
  /** The contents entry covering where the reader is, or null where none does. */
  currentTocHref: string | null;
  /** Null until a book with page numbers is on screen. */
  chapterProgress: EbookChapterProgress | null;
  /** Whether the book opened where it was asked to; null until one is on screen. */
  landedAt: OpenedEbook['landedAt'] | null;
  /** Null until a book is on screen: only an engine with one can report it. */
  fontSizeRange: [number, number] | null;
  selection: EbookSelection | null;
  next: () => void;
  previous: () => void;
  goTo: (location: EbookLocation) => void;
  clearSelection: () => void;
  /** Replaces what the reader draws over the book; remembered, so a reader rebuilt
   * by a retry is handed the current set. */
  applyDecorations: (decorations: EbookDecoration[]) => void;
  startSelectionExtension: () => void;
  cancelSelectionExtension: () => void;
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

/** One array before a book opens, so that a consumer holding `toc` as a prop or a
 * dependency is not handed a new one every render. */
const NO_TOC: EbookTocEntry[] = [];

/** One book opened into a host element, and where the reader is in it. */
export const useEbookReader = ({
  host,
  manifestUrl,
  enabled,
  canTurnPage,
  appearance,
  initialLocation,
  createReader = aReadiumReader,
  on,
  finishLanding,
}: UseEbookReaderOptions): EbookReaderState => {
  const [outcome, setOutcome] = useState<EbookReaderOutcome | null>(null);
  // Everything the book said as it opened, kept as the one value it arrived as.
  // Where the reader is moves on from it, so location and the contents entry are
  // seeded from it and then live on their own.
  const [opened, setOpened] = useState<OpenedEbook | null>(null);
  const [location, setLocation] = useState<EbookLocation | null>(null);
  const [currentTocHref, setCurrentTocHref] = useState<string | null>(null);
  const [chapterProgress, setChapterProgress] = useState<EbookChapterProgress | null>(null);
  const [selection, setSelection] = useState<EbookSelection | null>(null);
  const [attempt, setAttempt] = useState(0);
  const readerRef = useRef<EbookReader | null>(null);
  // Effect events rather than dependencies, so that the boot effect depends only
  // on what genuinely warrants rebuilding the reader: each of these is read at
  // the moment it is used, so a caller that rebinds a callback and a policy that
  // changes mid-book leave the book on screen alone. The same holds for the two
  // the book opens on — where a book opens and how it looks are settled when it
  // opens, and an answer arriving a second time cannot rebuild the reader around
  // it, while a retry opens on the current pair rather than the one from mount.
  const mayTurnPage = useEffectEvent(() => canTurnPage());
  const reportArrival = useEffectEvent((location: EbookLocation) => on?.arrivedAt?.(location));
  const reportMove = useEffectEvent((location: EbookLocation) => on?.movedTo?.(location));
  const activateDecoration = useEffectEvent((id: string) => on?.decorationActivated?.(id));
  const refuseExtension = useEffectEvent(() => on?.selectionExtensionRefused?.());
  const finishTheLanding = useEffectEvent((opened: OpenedEbook) => finishLanding?.(opened));
  const openingOptions = useEffectEvent(() => ({ appearance, initialLocation }));
  const appliedRef = useRef<EbookAppearance | null>(null);
  // What the reader draws over the book, kept here so that a reader built later has
  // something to be handed: the set belongs to the book, not to one reader of it.
  const decorationsRef = useRef<EbookDecoration[]>([]);
  // Whether a place has already been refused once. Never reset: the second
  // attempt offers nothing that could be rejected, so a second failure is real.
  const refusedRef = useRef(false);

  useEffect(() => {
    const element = host.current;
    if (!enabled || !element) return;

    const { appearance: openingAppearance, initialLocation: openingLocation } = openingOptions();
    const reader = createReader(element);
    readerRef.current = reader;
    // Whatever was handed over before this reader existed, or to the reader before it.
    reader.applyDecorations(decorationsRef.current);
    const offered = refusedRef.current ? null : openingLocation;
    const cancel = new AbortController();
    // Read through a call: TypeScript would carry a check's narrowing across an await.
    const isCancelled = () => cancel.signal.aborted;
    const signal = AbortSignal.any([cancel.signal, AbortSignal.timeout(BOOT_TIMEOUT_MS)]);
    let isOpen = false;
    const unsubscribes = [
      reader.onLocationChanged((location) => {
        setLocation(location);
        // Nothing a book reports before it has finished arriving is a move.
        if (isOpen) reportMove(location);
        else reportArrival(location);
        // Any report, a reflow included, leaves the selection's rectangle behind.
        reader.clearSelection();
      }),
      reader.onSelectionChanged(setSelection),
      reader.onTocEntryChanged(setCurrentTocHref),
      reader.onChapterProgressChanged(setChapterProgress),
      reader.onDecorationActivated((id) => activateDecoration(id)),
      reader.onSelectionExtensionRefused(() => refuseExtension()),
      reader.onPageTurnRequested((direction) => {
        // Readium's pager sets a navigating flag it never clears when it has no
        // frames yet, so one key before the book is up kills every later turn.
        if (!isOpen) return;
        if (!mayTurnPage()) return;
        void (direction === 'next' ? reader.next() : reader.previous());
      }),
    ];

    const onOpened = async (opened: OpenedEbook) => {
      if (isCancelled()) return;
      // The place the book settled on may never have been reported as a change,
      // so this is the only report a writer has to seed itself with.
      reportArrival(opened.location);
      setOpened(opened);
      setLocation(opened.location);
      setCurrentTocHref(opened.tocHref);
      setChapterProgress(opened.chapterProgress);
      const destination = finishTheLanding(opened);
      if (destination) {
        // A move that never finishes still owes the reader the book, where it opened.
        let timeout: ReturnType<typeof setTimeout> | undefined;
        await Promise.race([
          reader.goTo(destination).catch(() => {}),
          new Promise((resolve) => {
            timeout = setTimeout(resolve, FINISH_LANDING_TIMEOUT_MS);
          }),
        ]);
        clearTimeout(timeout);
        if (isCancelled()) return;
      }
      isOpen = true;
      setOutcome('open');
    };
    const onFailed = (error: unknown) => {
      // The one rejection that means nothing: this effect was cleaned up.
      if (isCancelled()) return;
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
    appliedRef.current = openingAppearance;
    const opening = reader.open(manifestUrl, {
      appearance: openingAppearance,
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
  }, [enabled, manifestUrl, attempt, createReader, host]);

  const next = useCallback(() => void readerRef.current?.next(), []);
  const previous = useCallback(() => void readerRef.current?.previous(), []);
  const goTo = useCallback(
    (destination: EbookLocation) => void readerRef.current?.goTo(destination),
    []
  );
  const clearSelection = useCallback(() => readerRef.current?.clearSelection(), []);
  const applyDecorations = useCallback((decorations: EbookDecoration[]) => {
    decorationsRef.current = decorations;
    readerRef.current?.applyDecorations(decorations);
  }, []);
  const startSelectionExtension = useCallback(
    () => readerRef.current?.startSelectionExtension(),
    []
  );
  const cancelSelectionExtension = useCallback(
    () => readerRef.current?.cancelSelectionExtension(),
    []
  );
  // Both, and in one go: the host is unmounted behind the message this is
  // offered on, and has to be back in the tree before the new attempt looks for it.
  const retry = useCallback(() => {
    setOutcome(null);
    // Nothing from the last attempt survives into the new one.
    setOpened(null);
    setCurrentTocHref(null);
    setChapterProgress(null);
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
    pageCount: opened?.pageCount ?? 0,
    location,
    toc: opened?.toc ?? NO_TOC,
    currentTocHref,
    chapterProgress,
    landedAt: opened?.landedAt ?? null,
    fontSizeRange: opened?.fontSizeRange ?? null,
    selection,
    next,
    previous,
    goTo,
    clearSelection,
    applyDecorations,
    startSelectionExtension,
    cancelSelectionExtension,
    retry,
  };
};
