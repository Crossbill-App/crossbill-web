import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
