import type { KnipConfig } from 'knip';

/**
 * Knip finds files, exports and dependencies nothing references any more.
 *
 * Run it with `npm run knip`. The route tree has to be generated first (the
 * script does that), otherwise every route file looks unreachable.
 *
 * Entry points are mostly discovered by knip's built-in Vite and Vitest
 * plugins: `index.html` pulls in `src/main.tsx`, and `vitest.config.ts`
 * contributes `src/**\/*.test.tsx` plus `tests/setup.ts`. Everything the
 * tests import (`tests/harness`, `tests/msw`, `tests/fixtures`) is reachable
 * from there, so it needs no entry of its own.
 */
const config: KnipConfig = {
  ignore: [
    // Regenerated wholesale by `npm run api:generate` from the backend's
    // OpenAPI schema. Orval emits a client for every endpoint whether or not
    // the frontend calls it, so unused exports here are expected and are not
    // ours to delete — the fix would be a backend change.
    'src/api/generated/**',
    // MSW's worker script, served as a static asset during tests rather than
    // imported, so nothing links to it.
    'tests/public/**',
  ],
  ignoreDependencies: [
    // Required by Vitest browser mode and loaded by the runner, never imported
    // by our own code.
    '@vitest/browser',
  ],
};

export default config;
