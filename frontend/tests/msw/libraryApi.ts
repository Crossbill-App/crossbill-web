import type { BookWithHighlightCount } from '@/api/generated/model';
import { http, HttpResponse } from 'msw';

/** The landing page's two lists, served from one set of books. */
export function libraryApi(books: BookWithHighlightCount[], recent: BookWithHighlightCount[] = []) {
  return [
    http.get('/api/v1/books/', () =>
      HttpResponse.json({ items: books, total: books.length, offset: 0, limit: 32 })
    ),
    http.get('/api/v1/books/recent', () => HttpResponse.json({ items: recent })),
  ];
}
