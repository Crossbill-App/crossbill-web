import { http, HttpResponse } from 'msw';

/**
 * A 1x1 transparent PNG, so an `<img>` pointed at a mocked cover actually
 * loads rather than firing `onError` and hiding itself — a hidden image drops
 * out of the accessibility tree, which would make `getByRole('img')` fail to
 * find it.
 */
const TRANSPARENT_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';

const transparentPngBytes = () =>
  Uint8Array.from(atob(TRANSPARENT_PNG_BASE64), (char) => char.charCodeAt(0));

/**
 * `GET /covers/:file`, answering every request with the same placeholder
 * image. `BookCover` prefixes the path with `API_BASE_URL`, which is empty
 * unless `VITE_API_URL` overrides it — and `vitest.config.ts` keeps env files
 * out of the test run, so the relative path matched here is what it requests.
 */
export const coversApi = () => [
  http.get(
    '/api/v1/covers/:file',
    () => new HttpResponse(transparentPngBytes(), { headers: { 'Content-Type': 'image/png' } })
  ),
];
