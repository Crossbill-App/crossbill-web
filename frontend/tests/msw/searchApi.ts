import type { GlobalSearchResults, RankedContentGroups } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';

const EMPTY_GROUPS: RankedContentGroups = { highlights: [], notes: [], digests: [] };
const EMPTY: GlobalSearchResults = { ...EMPTY_GROUPS, books: [] };

/**
 * `GET /search` answering from a query-text lookup table, so a test says what
 * "attention" matches and nothing else. An unlisted query answers with every
 * group empty, which is what "nothing matched" looks like.
 */
export const globalSearchApi = (byQuery: Record<string, Partial<GlobalSearchResults>>) => [
  http.get('/api/v1/search', ({ request }) => {
    const q = new URL(request.url).searchParams.get('q') ?? '';
    return HttpResponse.json({ ...EMPTY, ...(byQuery[q] ?? {}) });
  }),
];

/**
 * `GET /semantic/related` answering with one grouped body whatever the anchor.
 *
 * The score floor and the per-book cap are the endpoint's, so a test states
 * what came back rather than what was indexed — and a body that skips them is
 * how a test proves the client no longer filters on its own.
 */
export const relatedContentApi = (results: Partial<RankedContentGroups>) => [
  http.get('/api/v1/semantic/related', () => HttpResponse.json({ ...EMPTY_GROUPS, ...results })),
];
