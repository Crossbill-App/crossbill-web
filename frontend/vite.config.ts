import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Same origin in development, as production already has it. `changeOrigin` is
// pinned false because the string shorthand (`'/api': 'http://localhost:8000'`)
// forces it true: the backend builds the manifest's `self` link from the Host
// it sees, and a rewritten one sends every resource href past the proxy to
// :8000, cross-origin, where the reader's SameSite cookie and its same-origin
// iframe scripting both stop working.
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
