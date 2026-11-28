import { useGetDueFlashcards } from '@/api/generated/flashcards/flashcards.ts';
import type { DueFlashcard, PaginatedResponseDueFlashcard } from '@/api/generated/model';
import { useState } from 'react';

const PAGE_SIZE = 50;
const REFILL_AT = 5;

export interface QueuedFlashcard extends DueFlashcard {
  /** When the server answered with the card, which is the moment its previews count from. */
  fetchedAt: number;
}

interface LoadedQueue {
  response: PaginatedResponseDueFlashcard;
  cards: QueuedFlashcard[];
  firstTotal: number;
}

const mergeResponse = (
  loaded: LoadedQueue | null,
  response: PaginatedResponseDueFlashcard,
  fetchedAt: number
): LoadedQueue => {
  const fresh = new Map(response.items.map((card) => [card.id, { ...card, fetchedAt }]));
  const known = (loaded?.cards ?? []).map((card) => fresh.get(card.id) ?? card);
  const knownIds = new Set(known.map((card) => card.id));
  const added = [...fresh.values()].filter((card) => !knownIds.has(card.id));

  return {
    response,
    cards: [...known, ...added],
    firstTotal: loaded?.firstTotal ?? response.total,
  };
};

/**
 * The due flashcards of one review session, one at a time.
 *
 * Reviewed cards leave the server's due list, so the next page is the first
 * page fetched again; a card already in the session keeps its place and takes
 * the fresh copy's content.
 */
export const useReviewQueue = (bookId: number | undefined) => {
  const query = useGetDueFlashcards(
    { ...(bookId === undefined ? {} : { book_id: bookId }), limit: PAGE_SIZE },
    { query: { gcTime: 0 } }
  );
  const [loaded, setLoaded] = useState<LoadedQueue | null>(null);
  const [removedIds, setRemovedIds] = useState<readonly number[]>([]);

  if (query.data && query.data !== loaded?.response) {
    setLoaded(mergeResponse(loaded, query.data, query.dataUpdatedAt));
  }

  const remaining = (loaded?.cards ?? []).filter((card) => !removedIds.includes(card.id));
  const hasMore = loaded !== null && loaded.response.total > loaded.response.items.length;

  const remove = (flashcardId: number) => {
    setRemovedIds((ids) => [...ids, flashcardId]);
    if (hasMore && remaining.length - 1 <= REFILL_AT) {
      void query.refetch({ cancelRefetch: false });
    }
  };

  const restore = (flashcardId: number) =>
    setRemovedIds((ids) => ids.filter((id) => id !== flashcardId));

  return {
    current: remaining.length > 0 ? remaining[0] : null,
    position: removedIds.length + 1,
    total: Math.max(loaded?.firstTotal ?? 0, removedIds.length + remaining.length),
    isLoadError: loaded === null && query.isError,
    isDone: loaded !== null && remaining.length === 0 && !(hasMore && query.isFetching),
    remove,
    restore,
  };
};
