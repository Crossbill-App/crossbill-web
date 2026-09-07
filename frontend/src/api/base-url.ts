/**
 * Prefix every API URL is built from — the API's origin, or the empty string
 * when the API answers on the app's own origin.
 *
 * Empty by default, which makes every request relative to the page. That is
 * what production has always done (FastAPI serves the built frontend and the
 * API together) and what the Vite dev server now does too, by proxying `/api`
 * to the backend. Sharing an origin is not just tidiness: the reader loads
 * EPUB resources into iframes, and a cross-origin iframe cannot be scripted.
 *
 * `VITE_API_URL` overrides it for the setups that genuinely are cross-origin —
 * pointing a local frontend at a deployed backend, say. Expect the reader and
 * cookie-based refresh to be the parts that notice.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? '';
