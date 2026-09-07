import { playwright } from '@vitest/browser-playwright';
import path from 'path';
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

/**
 * The engines to run in — Chromium alone unless `TEST_BROWSERS` says otherwise.
 *
 * The web reader is the reason this is a knob at all. It leans on the browser
 * far harder than the rest of the app does (blob: documents, same-origin frames,
 * a `<meta>` CSP inside them), and those are exactly the places engines differ:
 * a book that would not open on iPhone Safari was a WebKit-only fault the
 * Chromium suite could not see. `TEST_BROWSERS=chromium,webkit npm run test`
 * runs both.
 */
const browsers = (process.env.TEST_BROWSERS ?? 'chromium')
  .split(',')
  .map((name) => name.trim())
  .filter(Boolean);

export default mergeConfig(
  viteConfig,
  defineConfig({
    // Serves tests/public/mockServiceWorker.js during tests only, so the worker
    // script never ends up in the production build.
    publicDir: 'tests/public',
    // Matches no variable name, so `import.meta.env` carries none of them —
    // neither a developer's frontend/.env nor a variable exported in the
    // shell or set by CI. Both reach a normal Vite build, and either would
    // compile `VITE_API_URL=http://localhost:8000` into `API_BASE_URL`; the
    // covers a page renders would then be fetched from that origin while the
    // MSW handlers wait on relative paths. Restricting the env *directory*
    // stops only the file half of that.
    envPrefix: [],
    resolve: {
      alias: {
        '@tests': path.resolve(import.meta.dirname,'./tests'),
      },
    },
    // Pre-bundled up front: discovering these mid-run makes Vite reload the page
    // and Vitest reports the reload as a failed test.
    optimizeDeps: {
      include: ['react/jsx-dev-runtime', 'react-dom/client'],
    },
    test: {
      include: ['src/**/*.test.tsx'],
      setupFiles: ['./tests/setup.ts'],
      browser: {
        enabled: true,
        headless: true,
        provider: playwright(),
        instances: browsers.map((browser) => ({ browser })),
        viewport: { width: 1440, height: 900 },
      },
    },
  })
);
