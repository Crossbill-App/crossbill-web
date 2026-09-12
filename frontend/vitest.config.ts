import { playwright } from '@vitest/browser-playwright';
import path from 'path';
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

// The `/api` proxy belongs to `vite dev`. Inherited here it would carry a
// request MSW did not handle through to the real backend, so a test missing a
// handler for a mutating endpoint would write to the developer's database
// instead of failing at the dev server.
const { server: _server, preview: _preview, ...viteConfigWithoutProxy } = viteConfig;

export default mergeConfig(
  viteConfigWithoutProxy,
  defineConfig({
    // Serves tests/public/mockServiceWorker.js during tests only, so the worker
    // script never ends up in the production build.
    publicDir: 'tests/public',
    // A shell or CI `VITE_API_URL`, or a developer's frontend/.env, would
    // compile a real origin into `API_BASE_URL` while the MSW handlers wait on
    // relative paths.
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
        instances: [{ browser: 'chromium' }],
        viewport: { width: 1440, height: 900 },
      },
    },
  })
);
