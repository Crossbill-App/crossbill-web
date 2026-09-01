import type { BookWithHighlightCount, LibraryActivity, LibraryStats } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';

/**
 * The library's list and the dashboard's recent row and activity grid, from one
 * set of books. The grid is empty by default, which is how the dashboard is
 * told there is no year to draw.
 */
export function libraryApi(
  books: BookWithHighlightCount[],
  recent: BookWithHighlightCount[] = [],
  activity: LibraryActivity | null = null,
  stats: LibraryStats | null = null
) {
  return [
    http.get('/api/v1/books/', () =>
      HttpResponse.json({ items: books, total: books.length, offset: 0, limit: 32 })
    ),
    http.get('/api/v1/books/recent', () => HttpResponse.json({ items: recent })),
    http.get('/api/v1/statistics/reading-activity', () => HttpResponse.json({ activity, stats })),
  ];
}
