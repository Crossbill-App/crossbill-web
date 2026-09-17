import {
  createHighlight,
  getGetBookHighlightLocatorsQueryKey,
  getGetBookHighlightLocatorsQueryOptions,
  getHighlightLocator,
} from '@/api/generated/highlights/highlights.ts';
import type {
  CollectionResponseHighlightLocatorResponse,
  HighlightLocatorResponse,
} from '@/api/generated/model';
import type { EbookDecoration, EbookLocation } from '@/components/reader/engine/EbookReader.ts';
import { standInDecoration } from '@/components/reader/highlights/decorations.ts';
import { LOCATORS_QUERY } from '@/components/reader/highlights/highlightLocatorsQuery.ts';
import type { HighlightColor } from '@/components/reader/highlights/highlightPalette.ts';
import { useSnackbar } from '@/context/SnackbarContext.tsx';
import { useMutationErrorHandler } from '@/hooks/useMutationErrorHandler.ts';
import { useCacheEvents } from '@/lib/cacheEvents.ts';
import { useQueryClient } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import { useRef, useState } from 'react';

// 422: the words matched in several places or none, and more context settles the first.
const REFUSALS: Record<number, string | undefined> = {
  422: "Couldn't find where this passage is in the book, so it wasn't highlighted. Try selecting a little more text.",
  503: "The book's file couldn't be read, so the highlight wasn't saved.",
};

const withLocator = (
  cached: CollectionResponseHighlightLocatorResponse,
  item: HighlightLocatorResponse
): CollectionResponseHighlightLocatorResponse => ({
  ...cached,
  items: [
    ...cached.items.filter((candidate) => candidate.highlight_id !== item.highlight_id),
    item,
  ],
});

export interface HighlightCreation {
  /** Passages drawn at once for highlights the server has not yet stored. */
  standIns: EbookDecoration[];
  create: (location: EbookLocation, color?: HighlightColor) => void;
}

/** Highlights made from selections in one book, each drawn before the server has answered. */
export const useHighlightCreation = (bookId: number): HighlightCreation => {
  const queryClient = useQueryClient();
  const { highlightCreated } = useCacheEvents();
  const { showSnackbar } = useSnackbar();
  const handleMutationError = useMutationErrorHandler();
  const [standIns, setStandIns] = useState<EbookDecoration[]>([]);
  const sequence = useRef(0);

  const placeLocator = async (highlightId: number) => {
    try {
      const item = await getHighlightLocator(highlightId);
      const loaded = await queryClient.ensureQueryData(
        getGetBookHighlightLocatorsQueryOptions(bookId, { query: LOCATORS_QUERY })
      );
      queryClient.setQueryData<CollectionResponseHighlightLocatorResponse>(
        getGetBookHighlightLocatorsQueryKey(bookId),
        (cached = loaded) => withLocator(cached, item)
      );
    } catch {
      // A highlight the server cannot place is not drawn, which is the rule for every other.
    }
  };

  const create = (location: EbookLocation, color?: HighlightColor) => {
    sequence.current += 1;
    const standIn = standInDecoration(sequence.current, location, color?.tint);
    setStandIns((current) => [...current, standIn]);

    void (async () => {
      try {
        const created = await createHighlight(bookId, {
          locator: location,
          device_color: color?.device_color,
        });
        await placeLocator(created.id);
        // Awaited so the stand-in stays until the saved highlight can be drawn.
        await highlightCreated(bookId);
      } catch (error) {
        const message = REFUSALS[(error as AxiosError).response?.status ?? 0];
        if (message) showSnackbar(message, 'error');
        else handleMutationError('save the highlight')(error);
      } finally {
        setStandIns((current) => current.filter((candidate) => candidate !== standIn));
      }
    })();
  };

  return { standIns, create };
};
