import type {
  EbookLocation,
  EbookReader,
  OpenedEbook,
  PageTurnDirection,
} from '@/components/reader/EbookReader.ts';

/** A place in the two-chapter book the other fixtures describe. */
export const aFakeLocation = (position: number): EbookLocation => ({
  href: `resources/OEBPS/chapter${position}.xhtml`,
  type: 'application/xhtml+xml',
  locations: { position },
});

/** An `EbookReader` whose open the test settles and whose events the test fires. */
export class FakeEbookReader implements EbookReader {
  readonly openedWith: string[] = [];
  nextCalls = 0;
  previousCalls = 0;
  destroyed = false;

  private readonly locationListeners = new Set<(location: EbookLocation) => void>();
  private readonly pageTurnListeners = new Set<(direction: PageTurnDirection) => void>();
  private settle: ((opened: OpenedEbook) => void) | undefined;
  private isOpened = false;

  async open(manifestUrl: string, signal?: AbortSignal): Promise<OpenedEbook> {
    signal?.throwIfAborted();
    if (this.isOpened) throw new Error('A reader opens one book; build another one.');
    this.isOpened = true;
    this.openedWith.push(manifestUrl);
    return await new Promise<OpenedEbook>((resolve, reject) => {
      this.settle = resolve;
      // The interface's contract, and the only way a boot watchdog can reach an
      // open that is going nowhere.
      signal?.addEventListener('abort', () => reject(signal.reason), { once: true });
    });
  }

  resolveOpen(opened: Partial<OpenedEbook> = {}): void {
    this.settle?.({ pageCount: 2, toc: [], location: aFakeLocation(1), ...opened });
  }

  requestPageTurn(direction: PageTurnDirection): void {
    for (const listener of [...this.pageTurnListeners]) listener(direction);
  }

  next(): Promise<void> {
    this.nextCalls += 1;
    return Promise.resolve();
  }

  previous(): Promise<void> {
    this.previousCalls += 1;
    return Promise.resolve();
  }

  goTo(): Promise<void> {
    return Promise.resolve();
  }

  onLocationChanged(listener: (location: EbookLocation) => void): () => void {
    this.locationListeners.add(listener);
    return () => this.locationListeners.delete(listener);
  }

  onPageTurnRequested(listener: (direction: PageTurnDirection) => void): () => void {
    this.pageTurnListeners.add(listener);
    return () => this.pageTurnListeners.delete(listener);
  }

  destroy(): Promise<void> {
    this.destroyed = true;
    return Promise.resolve();
  }
}
