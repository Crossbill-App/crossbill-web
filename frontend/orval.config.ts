import { defineConfig } from 'orval';

export default defineConfig({
  crossbill: {
    input: {
      target: '../backend/openapi.json',
    },
    output: {
      mode: 'tags-split',
      target: './src/api/generated',
      schemas: './src/api/generated/model',
      client: 'react-query',
      httpClient: 'axios',
      mock: false,
      clean: true,
      prettier: true,
      tsconfig: './tsconfig.json',
      override: {
        mutator: {
          path: './src/api/axios-instance.ts',
          name: 'axiosInstance',
        },
        query: {
          signal: true,
        },
      },
    },
  },
});
