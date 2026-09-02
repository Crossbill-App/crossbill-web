import type {
  BookWithHighlightCount,
  LibraryActivity,
  LibraryStats,
  RecentCapture,
} from '@/api/generated/model';
import { http, HttpResponse } from 'msw';

/**
 * The library's list and the dashboard's recent row, activity grid and capture
 * feed, from one set of books. The grid and the feed are empty by default,
 * which is how the dashboard is told there is neither a year to draw nor
 * anything captured.
 */
export function libraryApi(
  books: BookWithHighlightCount[],
  recent: BookWithHighlightCount[] = [],
  activity: LibraryActivity | null = null,
  stats: LibraryStats | null = null,
  captures: RecentCapture[] = []
) {
  return [
    http.get('/api/v1/books/', () =>
      HttpResponse.json({ items: books, total: books.length, offset: 0, limit: 32 })
    ),
    http.get('/api/v1/books/recent', () => HttpResponse.json({ items: recent })),
    http.get('/api/v1/statistics/reading-activity', () => HttpResponse.json({ activity, stats })),
    http.get('/api/v1/captures/recent', () => HttpResponse.json({ items: captures })),
  ];
}
