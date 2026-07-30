import { playwright } from '@vitest/browser-playwright';
import path from 'path';
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    // Serves tests/public/mockServiceWorker.js during tests only, so the worker
    // script never ends up in the production build.
    publicDir: 'tests/public',
    resolve: {
      alias: {
        '@tests': path.resolve(__dirname, './tests'),
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
