import type { PageViewUpdate } from '@/api/generated/model';
import type { EbookLocation, EbookScreen } from '@/components/reader/engine/EbookReader.ts';

/** A Page View that has ended, timed on `performance.now()`. */
export interface PageView {
  start: EbookLocation;
  end: EbookLocation;
  shownAt: number;
  durationMs: number;
}

interface OpenPageView {
  screen: EbookScreen;
  shownAt: number;
  countedMs: number;
  /** Null while the tab is hidden. */
  countingSince: number | null;
}

/**
 * The Page Views of one sitting: the one on screen, and the ended ones no write
 * has delivered yet.
 */
export const pageViewLog = () => {
  let latestScreen: EbookScreen | null = null;
  let isRecording = false;
  let isHidden = document.visibilityState === 'hidden';
  let current: OpenPageView | null = null;
  let undelivered: PageView[] = [];

  const begin = (screen: EbookScreen | null) => {
    const now = performance.now();
    current = screen && {
      screen,
      shownAt: now,
      countedMs: 0,
      countingSince: isHidden ? null : now,
    };
  };

  const endCurrent = () => {
    if (!current) return;
    const { screen, shownAt, countedMs, countingSince } = current;
    const runningMs = countingSince === null ? 0 : performance.now() - countingSince;
    undelivered.push({ ...screen, shownAt, durationMs: countedMs + runningMs });
    current = null;
  };

  return {
    /** Remembered before the book is on screen, so recording can start from it. */
    screenShown: (screen: EbookScreen | null) => {
      latestScreen = screen;
      if (!isRecording) return;
      endCurrent();
      begin(screen);
    },
    startRecording: () => {
      isRecording = true;
      begin(latestScreen);
    },
    endCurrent,
    hidden: () => {
      isHidden = true;
      if (!current || current.countingSince === null) return;
      current.countedMs += performance.now() - current.countingSince;
      current.countingSince = null;
    },
    shown: () => {
      isHidden = false;
      if (current && current.countingSince === null) current.countingSince = performance.now();
    },
    /** The ended Page Views, which are the caller's to deliver or give back. */
    take: (): PageView[] => {
      const batch = undelivered;
      undelivered = [];
      return batch;
    },
    /** A batch whose write failed, kept for the next one ahead of anything newer. */
    giveBack: (batch: PageView[]) => {
      undelivered = [...batch, ...undelivered];
    },
  };
};

/** The batch as a write sends it, its times as offsets from `sentAt`. */
export const pageViewUpdates = (batch: PageView[], sentAt: number): PageViewUpdate[] =>
  batch.map(({ start, end, shownAt, durationMs }) => ({
    start,
    end,
    shown_ms_before_send: Math.round(sentAt - shownAt),
    duration_ms: Math.round(durationMs),
  }));
