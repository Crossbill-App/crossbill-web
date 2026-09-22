import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

// Icons come from the registry, which gives each glyph one domain name and is
// what keeps two unrelated meanings from sharing one. The type is not an icon,
// so it stays importable anywhere.
const ICON_REGISTRY = {
  paths: [
    {
      name: '@mui/icons-material',
      allowTypeImports: true,
      message: 'Import icons from @/theme/Icons.tsx, adding one there if it is missing.',
    },
  ],
  patterns: [
    {
      group: ['@mui/icons-material/*'],
      message: 'Import icons from @/theme/Icons.tsx, adding one there if it is missing.',
    },
  ],
};

// Readium stays below the engine seam. The adapter and its own modules are what
// translate between the engine and the EbookReader interface; letting a hook or
// a component reach past them for a `Locator` would put Readium's types back in
// the UI and make a second engine impossible. Types are restricted too,
// deliberately: the seam exists so that its own types, not the engine's, are
// what cross it.
const READIUM_SEAM = {
  patterns: [
    {
      group: ['@readium/*'],
      message:
        'Only the engine adapter speaks Readium. Everything else goes through the EbookReader seam in @/components/reader/engine/EbookReader.ts.',
    },
  ],
};

// The component tier's boundary. `render` mounts a component on its own, which
// is the tier reserved for the directories below; everywhere else a `.test.tsx`
// drives a real route. `cleanup` is not restricted — a route test that renders
// twice still needs it.
const DIRECT_RENDER = {
  paths: [
    {
      name: 'vitest-browser-react',
      importNames: ['render'],
      message:
        'Behaviour tests drive a real route: use renderApp from @tests/harness/renderApp. Rendering a component on its own is the component tier, which is limited to the allowlist in frontend/claude.md > Testing.',
    },
  ],
};

/**
 * The directories whose `.test.tsx` files may render a component directly.
 * Each earns it by having behaviour a route test could not pin down — see
 * `frontend/claude.md > Testing` for what each one is and why.
 */
const COMPONENT_TIER = [
  'src/components/reader/**/*.test.tsx',
  'src/components/carousel/**/*.test.tsx',
  'src/hooks/**/*.test.tsx',
];

const SENTENCE_TEXT_QUERY_MESSAGE =
  'Assert the state, not the sentence: reach for the role and accessible name that state goes by ' +
  "(getByRole('status'), getByRole('alertdialog', { name: /delete/i })), adding the role or label in " +
  'src/ if it has none. Fixture prose belongs in a named constant, and a message that is itself the ' +
  'behaviour under test is asserted from one — once.';

// Invalidation belongs in src/lib/cacheEvents.ts, which owns the query keys and
// takes them from the generated getters. A hand-written key elsewhere once
// matched nothing and left deleted books in the list for five minutes.
// `setQueryData` is deliberately not restricted: optimistic updates, cache
// seeding and write-through are not invalidation and belong at their call site.
const CACHE_INVALIDATION = [
  {
    selector: 'CallExpression[callee.property.name=/^(invalidateQueries|refetchQueries)$/]',
    message:
      'Express the change as an event in @/lib/cacheEvents.ts rather than invalidating a query key here.',
  },
];

// A test that quotes a whole sentence of copy back at the app breaks on every
// rewording, and the sentence-case and ellipsis conventions in claude.md mean
// rewording keeps happening. Trailing `.`, `?` or `!` is what tells a sentence
// from the formatted values `getByText` is for — `Duration 1h 11m`, `63%`,
// `Pages 102 – 115` — which stay allowed, because there the format is the
// behaviour.
const SENTENCE_TEXT_QUERY = [
  {
    selector: "CallExpression[callee.property.name='getByText'] > Literal[value=/[.?!]$/]",
    message: SENTENCE_TEXT_QUERY_MESSAGE,
  },
  {
    selector:
      "CallExpression[callee.property.name='getByText'] > Literal[regex.pattern=/\\\\[.?!]$/]",
    message: SENTENCE_TEXT_QUERY_MESSAGE,
  },
];

/**
 * Composes the import restrictions that apply to one set of files.
 *
 * Flat config replaces a rule's options wholesale when a later block names the
 * same rule, so a block restricting one thing silently drops every restriction
 * an earlier block put on the same file — which is how the icon-registry rule
 * came to be enforced on the reader engine and the tests alone. Each block
 * below therefore names every restriction its files are under.
 */
const restrictImports = (...restrictions) => [
  'error',
  {
    paths: restrictions.flatMap((restriction) => restriction.paths ?? []),
    patterns: restrictions.flatMap((restriction) => restriction.patterns ?? []),
  },
];

/** The same composition, for `no-restricted-syntax` and the same reason. */
const restrictSyntax = (...restrictions) => ['error', ...restrictions.flat()];

export default tseslint.config(
  {
    ignores: [
      'dist',
      'node_modules',
      'src/api/generated',
      'src/routeTree.gen.ts',
      'tests/public',
      '*.config.ts',
    ],
  },
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
      'no-restricted-syntax': restrictSyntax(CACHE_INVALIDATION),
    },
  },
  {
    // The one module allowed to invalidate, since it is where the keys live.
    files: ['src/lib/cacheEvents.ts'],
    rules: { 'no-restricted-syntax': 'off' },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    rules: {
      // The typescript-eslint variant, for `allowTypeImports`.
      '@typescript-eslint/no-restricted-imports': restrictImports(ICON_REGISTRY, READIUM_SEAM),
    },
  },
  {
    // The registry itself, which is where the icons are imported.
    files: ['src/theme/Icons.tsx'],
    rules: { '@typescript-eslint/no-restricted-imports': restrictImports(READIUM_SEAM) },
  },
  {
    // The adapter and its own modules: the seam's inside.
    files: ['src/components/reader/engine/**'],
    rules: { '@typescript-eslint/no-restricted-imports': restrictImports(ICON_REGISTRY) },
  },
  {
    // A test may reach past the seam to stand in for the engine.
    files: ['src/**/*.test.{ts,tsx}', 'tests/**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-restricted-imports': restrictImports(ICON_REGISTRY),
      'no-restricted-syntax': restrictSyntax(CACHE_INVALIDATION, SENTENCE_TEXT_QUERY),
    },
  },
  {
    // Outside the component tier, a rendering test renders a route.
    files: ['src/**/*.test.tsx'],
    ignores: COMPONENT_TIER,
    rules: {
      '@typescript-eslint/no-restricted-imports': restrictImports(ICON_REGISTRY, DIRECT_RENDER),
    },
  }
);
