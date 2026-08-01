---
name: frontend-design
description: Styling and design-system conventions — theme colors, MUI usage, typography. Use when styling components, adding colors, or making any visual/design change.
---

# Frontend design

This app has an established design system; consistency with it beats novelty.

- The MUI theme in `frontend/src/theme/theme.ts` is the source of truth for
  colors, typography, and component styling. Read it before styling anything.
- Never hard-code color values in component code — use theme tokens. If a
  genuinely new color is needed, add it to the theme's `customColors` section
  first and reference it from there.
- Style through MUI components and the `sx` prop. Use semantic components
  (`Button`, `IconButton`) — never `<Box component="button">`; the semantic
  components carry the accessibility and interaction behavior.
- The UI kit is kept in sync with a claude.ai/design project. When a change
  alters the design system itself (theme tokens, shared components), say so in
  the summary so the sync doesn't silently drift.
