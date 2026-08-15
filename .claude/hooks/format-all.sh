#!/bin/bash
# PostToolUse hook: auto-format and check files after Edit/Write.
# Backend uses ruff (via uv) + pyright; frontend uses the workspace scripts.
# Must run tools through `uv run` / `npm` with the correct working directory —
# bare `ruff`/`pyright` are not on PATH, which previously made this a silent no-op.

file_path=$(jq -r '.tool_input.file_path' 2>/dev/null)
[[ -z "$file_path" || "$file_path" == "null" ]] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(git -C "$(dirname "$file_path")" rev-parse --show-toplevel 2>/dev/null)}"
[[ -z "$root" ]] && exit 0

# Backend Python files
if [[ "$file_path" == "$root/backend/"*.py ]]; then
  (cd "$root/backend" && uv run ruff format "$file_path" && uv run ruff check --fix "$file_path" && uv run pyright "$file_path")
fi

# Frontend files
if [[ "$file_path" =~ \.(ts|tsx|js|jsx)$ ]]; then
  (cd "$root/frontend" && npm run format -- "$file_path" && npm run lint -- "$file_path")
fi

exit 0
