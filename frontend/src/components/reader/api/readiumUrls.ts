/**
 * The reader's own Readium routes, spelled once.
 *
 * Absolute rather than relative: the manifest URL becomes the publication's
 * self link and so the base every chapter is resolved against, and the position
 * URL is fetched with `keepalive` by hand, outside the generated client.
 */
import { API_BASE_URL } from '@/api/base-url.ts';

const bookUrl = (bookId: number, path: string) =>
  new URL(`${API_BASE_URL}/api/v1/readium/books/${bookId}/${path}`, window.location.origin).href;

/** Where the book's manifest is published. */
export const manifestUrl = (bookId: number) => bookUrl(bookId, 'manifest.json');

/** Where the reader's place in one book is written down. */
export const readingPositionUrl = (bookId: number) => bookUrl(bookId, 'reading-position');
