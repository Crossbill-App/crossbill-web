import type { EbookLocation } from '@/components/reader/engine/EbookReader.ts';
import { useRouter } from '@tanstack/react-router';
import { useCallback, useRef } from 'react';

interface ReaderPlace {
  bookId: number;
  location: EbookLocation;
}

const placeIn = (state: unknown): ReaderPlace | undefined =>
  (state as { readerPlace?: ReaderPlace } | null)?.readerPlace;

const isSamePlace = (location: EbookLocation, other: EbookLocation | null) =>
  JSON.stringify(location) === JSON.stringify(other);

/**
 * Gives each link followed in the book a history entry, so Back returns to where it was followed from.
 * Each entry remembers the book's last place while current; a dialog's entry shares the one under it.
 */
export const useLinkHistory = (bookId: number) => {
  const { history } = useRouter();
  const hereRef = useRef<EbookLocation | null>(null);

  const record = useCallback(
    (location: EbookLocation) => {
      hereRef.current = location;
      // The unpatched method, beside the router's own keys: the router wraps
      // `window.history`'s copy to re-match the route, and a page turn changes no route.
      History.prototype.replaceState.call(
        window.history,
        { ...window.history.state, readerPlace: { bookId, location } },
        ''
      );
    },
    [bookId]
  );

  const linkFollowed = useCallback(() => {
    if (hereRef.current) record(hereRef.current);
    history.push(history.location.href);
    // Pushed now rather than on the router's microtask, so the move the link
    // causes cannot be recorded into the entry it left.
    history.flush();
  }, [history, record]);

  /** A Back or Forward onto an entry that remembers another place than the book is at. */
  const onReturn = useCallback(
    (listener: (location: EbookLocation) => void) => {
      const returnOnPop = () => {
        const place = placeIn(window.history.state);
        if (place?.bookId !== bookId || isSamePlace(place.location, hereRef.current)) return;
        listener(place.location);
      };
      window.addEventListener('popstate', returnOnPop);
      return () => window.removeEventListener('popstate', returnOnPop);
    },
    [bookId]
  );

  return { record, linkFollowed, onReturn };
};
