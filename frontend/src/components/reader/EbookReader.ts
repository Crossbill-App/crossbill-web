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
  /** Empty for the many manifests whose contents links declare no media type. */
  type: string;
  title: string;
  children: EbookTocEntry[];
}

/** What a book says about itself once it is on screen. */
export interface OpenedEbook {
  pageCount: number;
  toc: EbookTocEntry[];
  /** The contents entry the book opened at, or null where none covers it. */
  tocHref: string | null;
  location: EbookLocation;
  /** The range the engine honours for `EbookAppearance.fontSize`; any value inside it is legal. */
  fontSizeRange: [number, number];
}

/** How the page should look, in terms any engine can honour. */
export interface EbookAppearance {
  /** A multiplier on the publication's own font size; 1 is the book as its publisher set it. */
  fontSize: number;
  /** `null` says nothing at all, leaving the book's own stylesheet in charge. */
  textAlign: 'start' | 'justify' | null;
  /** `null` fits as many columns as the width allows. */
  columnCount: number | null;
  pageBackgroundColor: string;
  pageTextColor: string;
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

export interface OpenEbookOptions {
  /** Handed to the engine at construction, so the book opens at the right size
   * rather than reflowing a tick after it appears. */
  appearance: EbookAppearance;
  /** The caller's cancellation — an unmount, a remount, a boot watchdog — which
   * every await inside observes, composed with the reader's own destruction. */
  signal?: AbortSignal;
}

/** A book on screen, and the ways the UI moves through it. */
export interface EbookReader {
  /** Loads the book named by a Readium manifest URL into the host element. Call once. */
  open(manifestUrl: string, options: OpenEbookOptions): Promise<OpenedEbook>;
  /** Applies an appearance to a book already on screen. */
  setAppearance(appearance: EbookAppearance): Promise<void>;
  next(): Promise<void>;
  previous(): Promise<void>;
  goTo(location: EbookLocation): Promise<void>;
  onLocationChanged(listener: (location: EbookLocation) => void): () => void;
  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void;
  /** The reader has moved into a different contents entry; `OpenedEbook.tocHref` is the first. */
  onTocEntryChanged(listener: (href: string | null) => void): () => void;
  destroy(): Promise<void>;
}
