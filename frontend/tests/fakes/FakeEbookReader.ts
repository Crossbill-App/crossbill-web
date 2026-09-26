import type {
  EbookAppearance,
  EbookChapterProgress,
  EbookDecoration,
  EbookLocation,
  EbookReader,
  EbookSelection,
  OpenEbookOptions,
  OpenedEbook,
  PageTurnDirection,
} from '@/components/reader/engine/EbookReader.ts';

/** A place in the two-chapter book the other fixtures describe: 0% into it on page 1, 50% on page 2. */
export const aFakeLocation = (position: number): EbookLocation => ({
  href: `resources/OEBPS/chapter${position}.xhtml`,
  type: 'application/xhtml+xml',
  locations: { position, totalProgression: (position - 1) / 2 },
});

/** An `EbookReader` whose open the test settles and whose events the test fires. */
export class FakeEbookReader implements EbookReader {
  readonly openedWith: {
    manifestUrl: string;
    appearance: EbookAppearance;
    initialLocation?: EbookLocation;
  }[] = [];
  readonly appearances: EbookAppearance[] = [];
  readonly goToCalls: EbookLocation[] = [];
  /** One entry per call, so a test can assert on the set and on how often it was submitted. */
  readonly decorations: EbookDecoration[][] = [];
  /** What every `goTo` returns, so a test can hold one pending. */
  goToOutcome: Promise<void> = Promise.resolve();
  nextCalls = 0;
  previousCalls = 0;
  clearSelectionCalls = 0;
  startSelectionExtensionCalls = 0;
  cancelSelectionExtensionCalls = 0;
  destroyed = false;

  private readonly extensionRefusedListeners = new Set<() => void>();
  private readonly locationListeners = new Set<(location: EbookLocation) => void>();
  private readonly pageTurnListeners = new Set<(direction: PageTurnDirection) => void>();
  private readonly tocEntryListeners = new Set<(href: string | null) => void>();
  private readonly chapterProgressListeners = new Set<
    (progress: EbookChapterProgress | null) => void
  >();
  private readonly decorationListeners = new Set<(id: string) => void>();
  private readonly linkListeners = new Set<() => void>();
  private readonly selectionListeners = new Set<(selection: EbookSelection | null) => void>();
  private settle: ((opened: OpenedEbook) => void) | undefined;
  private refuse: ((reason: Error) => void) | undefined;
  private isOpened = false;

  async open(
    manifestUrl: string,
    { appearance, initialLocation, signal }: OpenEbookOptions
  ): Promise<OpenedEbook> {
    signal?.throwIfAborted();
    if (this.isOpened) throw new Error('A reader opens one book; build another one.');
    this.isOpened = true;
    this.openedWith.push({ manifestUrl, appearance, initialLocation });
    return await new Promise<OpenedEbook>((resolve, reject) => {
      this.settle = resolve;
      this.refuse = reject;
      // The interface's contract, and the only way a boot watchdog can reach an
      // open that is going nowhere.
      signal?.addEventListener('abort', () => reject(signal.reason), { once: true });
    });
  }

  resolveOpen(opened: Partial<OpenedEbook> = {}): void {
    this.settle?.({
      pageCount: 2,
      toc: [],
      tocHref: null,
      location: aFakeLocation(1),
      chapterProgress: null,
      landedAt: 'start',
      // Deliberately not the engine's own [0.7, 4], so a test about the
      // stepper's limits proves the range crossed the seam.
      fontSizeRange: [0.6, 2],
      ...opened,
    });
  }

  /** The engine refusing to open the book, as a navigator given a bad place does. */
  rejectOpen(reason = new Error('The book would not open.')): void {
    this.refuse?.(reason);
  }

  requestPageTurn(direction: PageTurnDirection): void {
    for (const listener of [...this.pageTurnListeners]) listener(direction);
  }

  reportLocation(location: EbookLocation): void {
    for (const listener of [...this.locationListeners]) listener(location);
  }

  reportTocEntry(href: string | null): void {
    for (const listener of [...this.tocEntryListeners]) listener(href);
  }

  reportChapterProgress(progress: EbookChapterProgress | null): void {
    for (const listener of [...this.chapterProgressListeners]) listener(progress);
  }

  /** A link in the book followed to wherever it points, as the engine reports it: first the link, then the move. */
  followLink(destination: EbookLocation): void {
    for (const listener of [...this.linkListeners]) listener();
    this.reportLocation(destination);
  }

  activateDecoration(id: string): void {
    for (const listener of [...this.decorationListeners]) listener(id);
  }

  select(selection: EbookSelection | null): void {
    for (const listener of [...this.selectionListeners]) listener(selection);
  }

  setAppearance(appearance: EbookAppearance): Promise<void> {
    this.appearances.push(appearance);
    return Promise.resolve();
  }

  next(): Promise<void> {
    this.nextCalls += 1;
    return Promise.resolve();
  }

  previous(): Promise<void> {
    this.previousCalls += 1;
    return Promise.resolve();
  }

  goTo(location: EbookLocation): Promise<void> {
    this.goToCalls.push(location);
    return this.goToOutcome;
  }

  applyDecorations(decorations: EbookDecoration[]): void {
    this.decorations.push(decorations);
  }

  onDecorationActivated(listener: (id: string) => void): () => void {
    this.decorationListeners.add(listener);
    return () => this.decorationListeners.delete(listener);
  }

  onSelectionChanged(listener: (selection: EbookSelection | null) => void): () => void {
    this.selectionListeners.add(listener);
    return () => this.selectionListeners.delete(listener);
  }

  clearSelection(): void {
    this.clearSelectionCalls += 1;
    this.select(null);
  }

  /** Lets the selection go, as the engine does when an extension starts. */
  startSelectionExtension(): void {
    this.startSelectionExtensionCalls += 1;
    this.select(null);
  }

  cancelSelectionExtension(): void {
    this.cancelSelectionExtensionCalls += 1;
  }

  onSelectionExtensionRefused(listener: () => void): () => void {
    this.extensionRefusedListeners.add(listener);
    return () => this.extensionRefusedListeners.delete(listener);
  }

  /** A tap the engine could not extend the selection with. */
  refuseSelectionExtension(): void {
    for (const listener of [...this.extensionRefusedListeners]) listener();
  }

  onLocationChanged(listener: (location: EbookLocation) => void): () => void {
    this.locationListeners.add(listener);
    return () => this.locationListeners.delete(listener);
  }

  onLinkFollowed(listener: () => void): () => void {
    this.linkListeners.add(listener);
    return () => this.linkListeners.delete(listener);
  }

  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void {
    this.pageTurnListeners.add(listener);
    return () => this.pageTurnListeners.delete(listener);
  }

  onTocEntryChanged(listener: (href: string | null) => void): () => void {
    this.tocEntryListeners.add(listener);
    return () => this.tocEntryListeners.delete(listener);
  }

  onChapterProgressChanged(listener: (progress: EbookChapterProgress | null) => void): () => void {
    this.chapterProgressListeners.add(listener);
    return () => this.chapterProgressListeners.delete(listener);
  }

  destroy(): Promise<void> {
    this.destroyed = true;
    return Promise.resolve();
  }
}
