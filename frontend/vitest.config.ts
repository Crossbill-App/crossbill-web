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
        instances: [{ browser: 'chromium' }],
        viewport: { width: 1440, height: 900 },
      },
    },
  })
);
