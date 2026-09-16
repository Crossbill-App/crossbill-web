/**
 * The seam between the UI and whatever engine puts a book on screen.
 *
 * Every command and event here is JSON-serialisable, so a `RemoteReader` in a
 * separate origin can implement the same interface over `postMessage`; the
 * trigger for building one is a book readable by someone other than its
 * uploader (#807). `onPageTurnRequested` is the contract that an arrow key
 * pressed anywhere while the reader is open reaches the UI as a request rather
 * than a turn: the UI decides whether to act on it.
 *
 * The seam holds in both directions. Nothing above this file imports
 * `@readium/*` -- ESLint enforces it, and only the engine adapter, its own
 * modules and tests are exempt -- so the types here, not the engine's, are what
 * the UI works in.
 * The engine below imports nothing from the UI, the API client or the app's
 * contexts, which is what lets it be swapped or moved to another origin.
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
    /** A querySelector-resolvable selector for the enclosing element. */
    cssSelector?: string;
  };
  /** The quoted words and their surroundings, which is what places a range rather than a page. */
  text?: { before?: string; highlight?: string; after?: string };
}

/** A range of the book drawn in a colour of its own. */
export interface EbookDecoration {
  id: string;
  location: EbookLocation;
  /** Six-digit hex, with the hash. */
  tint: string;
  opacity: number;
}

/** Where something is on the reader's screen, in the coordinates of the page the reader is on. */
export interface EbookRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * A passage the reader has selected in the book.
 *
 * The location is anchored well enough for another reader to find the same
 * words -- a selector for the element holding them, the quote, and the text on
 * either side -- which is what makes a selection into a highlight another
 * client can place. The rectangle is where those words are on screen, so
 * something can be put beside them.
 */
export interface EbookSelection {
  location: EbookLocation;
  rect: EbookRect;
  /** Whether the browser is still showing these words as selected; false for a passage
   * the engine is holding on to after the browser let go of it on its own. */
  shownAsSelected: boolean;
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
  /** Whether the place asked for named a resource this publication has; `'start'`
   * says the book opened at its beginning instead, and is what an apology hangs on. */
  landedAt: 'requested' | 'start';
  /** The range the engine honours for `EbookAppearance.fontSize`; any value inside it is legal. */
  fontSizeRange: [number, number];
}

/** How the page should look, in terms any engine can honour. */
export interface EbookAppearance {
  /** A multiplier on the publication's own font size; 1 is the book as its publisher set it. */
  fontSize: number;
  /** A multiplier on the font size; `null` leaves the book's own spacing alone. */
  lineHeight: number | null;
  /** The gap between paragraphs in rem; `null` leaves the book's own alone. */
  paragraphSpacing: number | null;
  /** The indent of a paragraph's first line in rem; `null` leaves the book's own alone. */
  paragraphIndent: number | null;
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
  /** Where the book should open; absent opens it at the beginning. */
  initialLocation?: EbookLocation;
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
  /** Replaces every decoration this reader draws. Safe before the book is on screen. */
  applyDecorations(decorations: EbookDecoration[]): void;
  /** A reader tapped one of the decorations, by its id. */
  onDecorationActivated(listener: (id: string) => void): () => void;
  /** What the reader has selected in the book, and `null` once they let it go. */
  onSelectionChanged(listener: (selection: EbookSelection | null) => void): () => void;
  /** Lets go of whatever the reader has selected in the book, and reports it let go. */
  clearSelection(): void;
  /** Remembers where the selection starts and lets it go, for the next tap to extend. */
  startSelectionExtension(): void;
  /** Forgets a remembered start, leaving the next tap in the book to do what it always does. */
  cancelSelectionExtension(): void;
  /** A tap that could not extend the selection, which today means one in another chapter. */
  onSelectionExtensionRefused(listener: () => void): () => void;
  onLocationChanged(listener: (location: EbookLocation) => void): () => void;
  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void;
  /** The reader has moved into a different contents entry; `OpenedEbook.tocHref` is the first. */
  onTocEntryChanged(listener: (href: string | null) => void): () => void;
  destroy(): Promise<void>;
}
