import {
  PublicationUnavailableError,
  type EbookLocation,
  type EbookReader,
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
  /** Must be referentially stable: an inline arrow rebuilds the reader every render. */
  createReader?: (host: HTMLElement) => EbookReader;
  bootTimeoutMs?: number;
}

export interface EbookReaderState {
  status: EbookReaderStatus;
  pageCount: number;
  location: EbookLocation | null;
  next: () => void;
  previous: () => void;
  retry: () => void;
}

const aReadiumReader = (host: HTMLElement): EbookReader => new ReadiumReader(host);

const outcomeOfFailure = (error: unknown): EbookReaderOutcome => {
  if (error instanceof PublicationUnavailableError) return error.reason;
  if (error instanceof DOMException && error.name === 'TimeoutError') return 'timeout';
  return 'error';
};

/** One book opened into a host element, and where the reader is in it. */
export const useEbookReader = ({
  host,
  manifestUrl,
  enabled,
  holdPageTurns,
  createReader = aReadiumReader,
  bootTimeoutMs = BOOT_TIMEOUT_MS,
}: UseEbookReaderOptions): EbookReaderState => {
  const [outcome, setOutcome] = useState<EbookReaderOutcome | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [location, setLocation] = useState<EbookLocation | null>(null);
  const [attempt, setAttempt] = useState(0);
  const readerRef = useRef<EbookReader | null>(null);
  // Through a ref, so a hold that starts mid-book never rebuilds the reader.
  const holdRef = useRef(holdPageTurns);
  useEffect(() => {
    holdRef.current = holdPageTurns;
  }, [holdPageTurns]);

  useEffect(() => {
    const element = host.current;
    if (!enabled || !element) return;

    const reader = createReader(element);
    readerRef.current = reader;
    const cancel = new AbortController();
    const signal = AbortSignal.any([cancel.signal, AbortSignal.timeout(bootTimeoutMs)]);
    let isOpen = false;
    const unsubscribes = [
      reader.onLocationChanged(setLocation),
      reader.onPageTurnRequested((direction) => {
        // Readium's pager sets a navigating flag it never clears when it has no
        // frames yet, so one key before the book is up kills every later turn.
        if (holdRef.current || !isOpen) return;
        void (direction === 'next' ? reader.next() : reader.previous());
      }),
    ];

    const onOpened = (opened: OpenedEbook) => {
      if (cancel.signal.aborted) return;
      isOpen = true;
      setPageCount(opened.pageCount);
      setLocation(opened.location);
      setOutcome('open');
    };
    const onFailed = (error: unknown) => {
      // The one rejection that means nothing: this effect was cleaned up.
      if (cancel.signal.aborted) return;
      setOutcome(outcomeOfFailure(error));
    };

    // The engine cannot cancel a fetch Readium itself started, so a hanging
    // resource would leave `open` pending long past the watchdog's deadline.
    const abortedFirst = new Promise<never>((_, reject) => {
      signal.addEventListener('abort', () => reject(signal.reason as Error), { once: true });
    });
    Promise.race([reader.open(manifestUrl, signal), abortedFirst]).then(onOpened, onFailed);

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
  // Both, and in one go: the host is unmounted behind the message this is
  // offered on, and has to be back in the tree before the new attempt looks for it.
  const retry = useCallback(() => {
    setOutcome(null);
    // Otherwise the last attempt's page label sits over the new attempt's skeleton.
    setPageCount(0);
    setAttempt((count) => count + 1);
  }, []);

  // Derived rather than stored, so that starting an attempt is not itself a
  // render: an effect that set the status would cascade one on every open.
  const status: EbookReaderStatus = enabled ? (outcome ?? 'opening') : 'idle';

  return { status, pageCount, location, next, previous, retry };
};
