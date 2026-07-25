import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'src/api/generated', 'src/routeTree.gen.ts', '*.config.ts'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        project: './tsconfig.json',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true, allowExportNames: ['Route'] },
      ],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-unnecessary-condition': 'warn',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      // Invalidation belongs in src/lib/cacheEvents.ts, which owns the query keys
      // and takes them from the generated getters. A hand-written key here once
      // matched nothing and left deleted books in the list for five minutes.
      // `setQueryData` is deliberately not restricted: optimistic updates, cache
      // seeding and write-through are not invalidation and belong at their call site.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            'CallExpression[callee.property.name=/^(invalidateQueries|refetchQueries)$/]',
          message:
            'Express the change as an event in @/lib/cacheEvents.ts rather than invalidating a query key here.',
        },
      ],
    },
  },
  {
    // The one module allowed to invalidate, since it is where the keys live.
    files: ['src/lib/cacheEvents.ts'],
    rules: { 'no-restricted-syntax': 'off' },
  }
);
