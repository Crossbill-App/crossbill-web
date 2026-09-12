/**
 * The seam between the UI and whatever engine puts a book on screen.
 *
 * Every command and event here is JSON-serialisable, so a `RemoteReader` in a
 * separate origin can implement the same interface over `postMessage`; the
 * trigger for building one is a book readable by someone other than its
 * uploader (#807). `onPageTurnRequested` is the contract that an arrow key
 * pressed anywhere while the reader is open reaches the UI as a request rather
 * than a turn: the UI decides whether to act on it.
 */

/** Where the reader is in the book, as JSON that can cross a postMessage boundary. */
export interface EbookLocation {
  href: string;
  type: string;
  title?: string;
  locations: {
    position?: number;
    progression?: number;
    totalProgression?: number;
    fragments?: string[];
  };
}

/** One heading of the book's table of contents. */
export interface EbookTocEntry {
  href: string;
  title: string;
  children: EbookTocEntry[];
}

/** What a book says about itself once it is on screen. */
export interface OpenedEbook {
  pageCount: number;
  toc: EbookTocEntry[];
  location: EbookLocation;
}

/** Which way a page turn was asked to go. */
export type PageTurnDirection = 'next' | 'previous';

/** Whether the book has no publication at all, or one that could not be read. */
export type PublicationUnavailableReason = 'missing' | 'error';

/** There is nothing to open: the book has no publication, or fetching it failed. */
export class PublicationUnavailableError extends Error {
  constructor(readonly reason: PublicationUnavailableReason) {
    super(`The publication is unavailable (${reason}).`);
    this.name = 'PublicationUnavailableError';
  }
}

/** A book on screen, and the ways the UI moves through it. */
export interface EbookReader {
  /**
   * Loads the book named by a Readium manifest URL into the host element. Call once.
   *
   * `signal` is the caller's cancellation (an unmount, a remount, a boot watchdog via
   * `AbortSignal.timeout`); every await inside observes it, composed with the reader's destruction.
   */
  open(manifestUrl: string, signal?: AbortSignal): Promise<OpenedEbook>;
  next(): Promise<void>;
  previous(): Promise<void>;
  goTo(location: EbookLocation): Promise<void>;
  onLocationChanged(listener: (location: EbookLocation) => void): () => void;
  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void;
  destroy(): Promise<void>;
}
