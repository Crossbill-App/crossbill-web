import type { SemanticSearchResults } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';

const EMPTY: SemanticSearchResults = { highlights: [], notes: [], digests: [] };

/**
 * `GET /semantic/search` answering from a query-text lookup table, so a test
 * says what "attention" matches and nothing else. An unlisted query answers
 * with all three groups empty, which is what "nothing matched" looks like.
 */
export const semanticSearchApi = (byQuery: Record<string, Partial<SemanticSearchResults>>) => [
  http.get('/api/v1/semantic/search', ({ request }) => {
    const q = new URL(request.url).searchParams.get('q') ?? '';
    return HttpResponse.json({ ...EMPTY, ...(byQuery[q] ?? {}) });
  }),
];
