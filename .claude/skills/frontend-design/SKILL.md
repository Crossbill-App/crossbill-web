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
- Icons come from `frontend/src/theme/Icons.tsx`, one glyph per domain name —
  an eslint rule blocks importing them from `@mui/icons-material` anywhere
  else. Size them from `ICON_SIZE` in `theme/iconSizes.ts` (`inline` 16, `ui`
  20, `prominent` 24), never below `ui` for something clickable.
