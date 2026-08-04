# Crossbill project site

The public site for Crossbill: the landing page, the user documentation, and an
unlisted blog section. Built with [Astro](https://astro.build/) and the
[Starlight](https://starlight.astro.build/) docs theme.

## Running it

```bash
cd site
npm install
npm run dev      # http://localhost:4321/crossbill-web/
npm run build    # static output in site/dist/
npm run preview  # serve the built output
```

The site is configured for GitHub Pages under a base path, so the dev server
serves it at `/crossbill-web/`, not `/`.

## Layout

- `src/content/docs/index.mdx` — the landing page (Starlight `splash` template).
- `src/content/docs/getting-started/`, `features/`, `integrations/` — the
  documentation. The sidebar is declared explicitly in `astro.config.mjs`; add a
  page there when you add a file.
- `src/content/blog/` — an unlisted blog collection. `src/pages/blog/` renders
  `/blog/` and one route per post. Nothing links to it from the navigation; drop
  a Markdown file into `src/content/blog/` with `title` and `date` frontmatter
  to start. Until then the build logs "The collection `blog` … is empty", which
  is expected.
- `src/styles/custom.css` — the theme, ported from the app's design source of
  truth, `frontend/src/theme/theme.ts`.

Internal links are written **relative** so they survive the `/crossbill-web`
base path; do not hard-code root-absolute paths like `/features/notes/`.

## Deployment

`.github/workflows/deploy-site.yml` builds and publishes to GitHub Pages on
every push to `main` that touches `site/**`, and on manual dispatch. The
repository's Pages source must be set to **GitHub Actions**.

## Writing docs

Use the project's ubiquitous language from `CONTEXT.md` at the repository root —
Highlight, Tag, Label, Chapter Digest, Note, Book Reflection, Flashcard, Reading
Stage, Reading Session, Bookmark. Do not describe features that do not exist.
