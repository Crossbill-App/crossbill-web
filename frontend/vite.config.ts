import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Puts the API on the local server's own origin, the way production already
// has it — FastAPI serves the built frontend and the API together. The reader
// loads EPUB resources into iframes and cannot script them across origins, so
// local development has to match. The target is the backend `make dev-app`
// starts; point it elsewhere here rather than setting VITE_API_URL, which
// gives up same origin along with the proxy.
// SPIKE #740: `changeOrigin` must be false. Vite rewrites the Host header by
// default, so the backend builds the manifest's `self` link (str(request.url))
// as http://localhost:8000/... — Readium resolves every resource href against
// that link, which sends the navigator's fetches and the blob document's <base>
// cross-origin, past the proxy, where the SameSite cookie and same-origin
// iframe scripting the reader depends on both stop working.
const apiProxy = {
  '/api': { target: 'http://localhost:8000', changeOrigin: false },
};

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname,'./src'),
      '@/components': path.resolve(import.meta.dirname,'./src/components'),
      '@/hooks': path.resolve(import.meta.dirname,'./src/hooks'),
      '@/utils': path.resolve(import.meta.dirname,'./src/utils'),
      '@/api': path.resolve(import.meta.dirname,'./src/api'),
      '@/types': path.resolve(import.meta.dirname,'./src/types'),
    },
  },
});
