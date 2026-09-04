import type { GlobalSearchResults } from '@/api/generated/model';
import { useGlobalSearch } from '@/api/generated/search/search.ts';
import { useSettings } from '@/context/SettingsContext.tsx';
import { keepPreviousData } from '@tanstack/react-query';

/** Default results per content type. The endpoint's maximum is 100. */
const DEFAULT_LIMIT = 25;

interface UseContentSearchOptions {
  /** Current query text. The caller owns where it is stored. */
  query: string;
  /** Scope to one book. Omit to search every book. */
  bookId?: number;
  /** Results per content type. Defaults to 25; the endpoint's maximum is 100. */
  limit?: number;
}

interface ContentSearchState {
  /** Groups as the endpoint ranked them, best first, plus the unranked `books`. */
  results: GlobalSearchResults | undefined;
  isFetching: boolean;
  isError: boolean;
  /**
   * True when embeddings are enabled and the trimmed query is non-empty —
   * i.e. the page should filter.
   */
  hasQuery: boolean;
}

/**
 * `GET /search` over the user's content, for any caller that owns a query box.
 *
 * Named for what it does at every call site rather than for the global search
 * it powers in the app bar: scoped to a `bookId` the endpoint matches no books
 * by name, so the read there is purely semantic over that one book's content.
 *
 * `results` is `undefined` until there is a query and an answer, so a page
 * branches on `hasQuery` rather than on emptiness: no search and "nothing
 * matched" are different states that must render differently.
 */
export const useContentSearch = ({
  query,
  bookId,
  limit = DEFAULT_LIMIT,
}: UseContentSearchOptions): ContentSearchState => {
  const { featureFlags } = useSettings();
  const q = query.trim();
  // Gated here, not just in the field: a page must never filter on a query
  // the user cannot see or clear because the flag hid the input that owns it.
  const hasQuery = featureFlags?.embeddings === true && q.length > 0;

  const { data, isFetching, isError } = useGlobalSearch(
    { q, book_id: bookId, limit },
    // `q` is a required param with minLength 1; `enabled` is what keeps an
    // empty query (or a disabled feature) off the wire. keepPreviousData
    // stops the filtered list flashing empty between keystrokes.
    { query: { enabled: hasQuery, placeholderData: keepPreviousData } }
  );

  // Weak matches are already gone: the endpoint holds a measured similarity
  // floor, so a group that comes back short is short on purpose.
  return { results: hasQuery ? data : undefined, isFetching, isError, hasQuery };
};
