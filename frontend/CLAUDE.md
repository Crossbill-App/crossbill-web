# Frontend

Hooks lint and format each edit and run knip, tsc and jscpd when a turn ends.
`npm run test` is not hooked: run it before calling work done. Before
writing, changing or reviewing a test, load the `writing-frontend-tests`
skill.

## Dead code (knip)

When knip reports a file, export or dependency nothing references, resolve it
in this order of preference:

1. **Delete it** — the usual answer.
2. **Un-export it** — if the symbol is used inside its own file, drop the
   `export` rather than the code.
3. **Ignore it** — only for things knip cannot see (assets loaded by a runner,
   generated output). Add it to `frontend/knip.config.ts` with a comment saying
   why.

A fake import or re-export that silences a finding is not a resolution.

## Generated code

`src/api/generated` is Orval output from the committed `backend/openapi.json`,
and `routeTree.gen.ts` is TanStack Router's. Regenerate them, never hand-edit
them; both are excluded from jscpd because the repetition is not ours to
refactor.

## Conventions

- Functional style: pure functions, immutable data, functional components with
  hooks; lodash for functional utilities (`groupBy`, `debounce`, `memoize`, …).
- Prefer interfaces over types for object shapes.
- Server state via TanStack Query; invalidate queries after mutations.
- Styling: MUI components, the `sx` prop, and theme tokens — conventions and
  the theme source of truth are in the `frontend-design` skill.
- Never native `alert()`/`confirm()`: use `useSnackbar` from
  `@/context/SnackbarContext.tsx` for transient feedback and
  `ConfirmationDialog` from `@/components/common/ConfirmationDialog.tsx` for
  destructive actions.
- User-facing copy uses three periods for an ellipsis (`Saving...`,
  `Search highlights...`), never the `…` character. Prose in comments and docs
  may use either.
- User-facing copy is sentence case — dialog titles, tooltips, buttons, form
  labels, section headings, tab labels. `Delete highlight`, not
  `Delete Highlight`; `Confirm new password`, not `Confirm New Password`. Only
  proper nouns keep their capitals (Crossbill, KOReader, and whatever the
  reader's own books and chapters are called). There is no lint rule for this:
  a checker cannot tell a proper noun from Title Case, so it is on review.
- One label for committing a form: **Save** for editing something that already
  exists, and a named create (**Add flashcard**, **Add group**) only where the
  form is one of several controls on screen. Pending states are the verb in
  sentence case plus an ellipsis — `Saving...`, never `Updating...`.

## UI copy (i18n)

Every user-facing string lives in `src/i18n/locales/en/`, read through
react-i18next — never written inline in a component. That is what lets the
copy be translated, and edited in one place. A lint rule rejects text between
JSX tags and literal `aria-label`/`title`/`placeholder`/`label`/`alt`/
`helperText`/`tooltip` values in `src/`.

- **One JSON file per area** (`highlights.json`, `reader.json`, …); the file
  name is its top-level key and `locales/en/index.ts` lists them. Keys nest by
  screen, then component, then purpose, so a key says where its text appears:
  `highlights.viewDialog.deleteConfirm.message`.
- **Shared text is defined once** in `common.json`: action verbs (`Save`,
  `Cancel`), states (`Saving...`), entity names (`Highlights`), fallbacks
  (`Unknown author`), form fields and validation. Reuse a common key only when
  the meaning is the same, not merely the spelling; text shared within one
  area goes under that area's `shared` key.
- **Components** call `const { t } = useTranslation()`. Plain modules import
  `i18n` from `@/i18n` and call `i18n.t` lazily, inside a function — never at
  module load, where it would freeze the language. Label maps hold keys, not
  text.
- **Never concatenate copy.** Interpolate (`{{count}}`, `{{title}}`) and use
  i18next plurals (`key_one` / `key_other`) with `count`; wrap sentences that
  contain markup in `<Trans>`.
- **Keys are typed** (`src/i18n/i18next.d.ts`): a missing or misspelled key
  fails `npm run type-check`. A dynamic key must be a union of literal keys.
