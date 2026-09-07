import { API_BASE_URL } from '@/api/base-url.ts';
import { useGetReadiumManifest } from '@/api/generated/readium/readium.ts';
import { HttpFetcher, Locator, Manifest, Publication } from '@readium/shared';
import Axios from 'axios';
import { useEffect, useMemo, useState } from 'react';

const isNotFound = (error: unknown) => Axios.isAxiosError(error) && error.response?.status === 404;

/**
 * The manifest is a book's structure, not its state: it only changes when the
 * EPUB behind it is replaced. Caching it for the session means the "Read" tab's
 * visibility probe and the reader itself share one request.
 */
const MANIFEST_QUERY = {
  staleTime: Infinity,
  // A missing EPUB answers 404, which is an answer, not a failure to retry.
  retry: false,
} as const;

const manifestUrl = (bookId: number) =>
  new URL(`${API_BASE_URL}/api/v1/readium/books/${bookId}/manifest.json`, window.location.origin)
    .href;

/**
 * Fetches everything the navigator loads, with the publication cookie attached.
 *
 * The resources of a book are not requests the app makes on its own behalf —
 * they are made by Readium, for iframes, and the credential that reaches an
 * iframe is a cookie. `credentials: 'include'` is what puts the cookie
 * `useReaderSession` minted on every one of them.
 */
const credentialedFetch: typeof fetch = (input, init) =>
  fetch(input, { ...init, credentials: 'include' });

/**
 * Whether this book has an EPUB the web reader can open.
 *
 * `undefined` while the answer is unknown, so a caller can tell "no EPUB" from
 * "not asked yet" and avoid flashing a tab that is about to disappear.
 *
 * The manifest is the only thing the API offers to ask with: `BookDetails`
 * carries no `has_ebook` flag, so presence is inferred from the manifest
 * answering rather than 404ing. That makes this a whole manifest parsed
 * server-side to decide whether to draw a tab, where a boolean on the
 * book-details view would do it for nothing. Cheap enough for now — the
 * manifest is cached per book and the reader reuses this very response — but
 * it is the thing to fix if the book page ever feels slow.
 */
export const useHasPublication = (bookId: number): boolean | undefined => {
  const { isError, isPending } = useGetReadiumManifest(bookId, { query: MANIFEST_QUERY });
  if (isPending) return undefined;
  return !isError;
};

type ReaderPublicationStatus = 'pending' | 'ready' | 'missing' | 'error';

export interface ReaderPublication {
  status: ReaderPublicationStatus;
  publication: Publication | undefined;
  /**
   * One locator per synthetic page — empty when the book publishes no position
   * list, and `undefined` until the list has been fetched at all.
   *
   * The distinction matters to the navigator: it takes its positions once, at
   * construction, so building it against a list that has not arrived yet means
   * rebuilding it (and losing the reader's place) the moment it does.
   */
  positions: Locator[] | undefined;
}

/**
 * Builds the Readium `Publication` the navigator reads from.
 *
 * The manifest arrives through the generated client (Bearer, axios, the app's
 * own interceptors) and everything the manifest names is fetched by Readium
 * through `credentialedFetch`. The self link is set to the URL actually
 * fetched rather than trusted from the body: every resource href in the
 * manifest is relative to it, and resolving them against this origin is what
 * keeps the iframes same-origin and scriptable.
 */
export const useReaderPublication = (bookId: number): ReaderPublication => {
  const { data, error, isPending } = useGetReadiumManifest(bookId, { query: MANIFEST_QUERY });
  const [positions, setPositions] = useState<Locator[] | undefined>(undefined);

  const publication = useMemo(() => {
    if (data === undefined) return undefined;
    const manifest = Manifest.deserialize(data);
    if (!manifest) return undefined;
    const selfHref = manifestUrl(bookId);
    manifest.setSelfLink(selfHref);
    return new Publication({
      manifest,
      fetcher: new HttpFetcher(credentialedFetch, selfHref),
    });
  }, [bookId, data]);

  useEffect(() => {
    if (!publication) return;
    let cancelled = false;
    // A book whose position list cannot be read is still readable; it just
    // cannot say which page you are on.
    publication
      .positionsFromManifest()
      .then((locators) => {
        if (!cancelled) setPositions(locators);
      })
      .catch(() => {
        if (!cancelled) setPositions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [publication]);

  const status = ((): ReaderPublicationStatus => {
    if (isPending) return 'pending';
    // 404 is the API saying this book has no EPUB (or no such book), which is
    // an empty state rather than a failure. Anything else really did go wrong.
    if (error) return isNotFound(error) ? 'missing' : 'error';
    return publication ? 'ready' : 'error';
  })();

  return { status, publication, positions };
};
