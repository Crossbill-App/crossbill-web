/**
 * Prefix every API URL is built on — empty unless `VITE_API_URL` names a
 * cross-origin backend. Same origin is a requirement, not tidiness: the reader
 * scripts EPUB resources loaded into iframes, which a cross-origin document
 * forbids.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? '';
