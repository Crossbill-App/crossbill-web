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
}

const isComplete = (response: PaginatedResponseDueFlashcard) =>
  response.total <= response.items.length;

/** A complete response also drops the unreviewed cards it no longer lists: they left review elsewhere. */
const mergeResponse = (
  loaded: LoadedQueue | null,
  response: PaginatedResponseDueFlashcard,
  fetchedAt: number,
  removedIds: ReadonlySet<number>
): LoadedQueue => {
  const fresh = new Map(response.items.map((card) => [card.id, { ...card, fetchedAt }]));
  const known = (loaded?.cards ?? [])
    .filter((card) => fresh.has(card.id) || removedIds.has(card.id) || !isComplete(response))
    .map((card) => fresh.get(card.id) ?? card);
  const knownIds = new Set(known.map((card) => card.id));
  const added = [...fresh.values()].filter((card) => !knownIds.has(card.id));

  return { response, cards: [...known, ...added] };
};

/** Reviewed cards leave the due list, so the next page is the first page fetched again. */
export const useReviewQueue = (bookId: number | undefined) => {
  const query = useGetDueFlashcards(
    { ...(bookId === undefined ? {} : { book_id: bookId }), limit: PAGE_SIZE },
    { query: { gcTime: 0 } }
  );
  const [loaded, setLoaded] = useState<LoadedQueue | null>(null);
  const [removedIds, setRemovedIds] = useState<ReadonlySet<number>>(new Set());

  if (query.data && query.data !== loaded?.response) {
    setLoaded(mergeResponse(loaded, query.data, query.dataUpdatedAt, removedIds));
  }

  const remaining = (loaded?.cards ?? []).filter((card) => !removedIds.has(card.id));
  const unfetched = loaded ? loaded.response.total - loaded.response.items.length : 0;
  const hasMore = unfetched > 0;

  const remove = (flashcardId: number) => {
    setRemovedIds((ids) => new Set(ids).add(flashcardId));
    if (hasMore && remaining.length - 1 <= REFILL_AT) {
      void query.refetch();
    }
  };

  const restore = (flashcardId: number) =>
    setRemovedIds((ids) => new Set([...ids].filter((id) => id !== flashcardId)));

  return {
    current: remaining.length > 0 ? remaining[0] : null,
    position: removedIds.size + 1,
    total: removedIds.size + remaining.length + unfetched,
    isLoadError: remaining.length === 0 && query.isError,
    isDone:
      loaded !== null && remaining.length === 0 && !query.isError && !(hasMore && query.isFetching),
    retry: () => void query.refetch(),
    remove,
    restore,
  };
};
