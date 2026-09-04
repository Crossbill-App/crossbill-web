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
  /**
   * Whether this caller's results are worth asking for without embeddings.
   * True by default: a book-scoped search ranks content and nothing else, so
   * with the feature off it can only answer empty. The app bar sets it false —
   * its books are matched by name, which needs no vectors.
   */
  requiresEmbeddings?: boolean;
}

interface ContentSearchState {
  /** Groups as the endpoint ranked them, best first, plus the unranked `books`. */
  results: GlobalSearchResults | undefined;
  isFetching: boolean;
  isError: boolean;
  /** True when the trimmed query is non-empty and searchable — i.e. the page should filter. */
  hasQuery: boolean;
}

/**
 * `GET /search` over the user's content, for any caller that owns a query box.
 *
 * Named for what it does at every call site rather than for the global search
 * it powers in the app bar: scoped to a `bookId` the endpoint matches no books
 * by name, so the read there is purely semantic over that one book's content.
 * Unscoped it also matches books by title and author, which is why the app bar
 * searches on a server with no embedding provider and the book tabs do not.
 *
 * `results` is `undefined` until there is a query and an answer, so a page
 * branches on `hasQuery` rather than on emptiness: no search and "nothing
 * matched" are different states that must render differently.
 */
export const useContentSearch = ({
  query,
  bookId,
  limit = DEFAULT_LIMIT,
  requiresEmbeddings = true,
}: UseContentSearchOptions): ContentSearchState => {
  const { featureFlags } = useSettings();
  const q = query.trim();
  const isSearchable = !requiresEmbeddings || featureFlags?.embeddings === true;
  // Gated here, not just in the field: the book tabs keep their query in the
  // URL, so a shared `?search=` link must not filter a list whose input the
  // flag has hidden.
  const hasQuery = isSearchable && q.length > 0;

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
