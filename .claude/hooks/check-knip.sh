#!/bin/bash
# Stop hook: verify knip finds no unused files, exports or dependencies.
# Dead code only shows up once a change is complete — a symbol looks unused
# halfway through an edit — so this runs per-turn rather than per-edit
# (alongside format-all.sh). Costs <1s, and only fires when frontend sources or
# package.json are dirty. CI enforces the same check via `npm run knip`.

input=$(cat)

# Claude Code sets this when the stop was already blocked once — bail so we can't loop.
[[ "$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null)" == "true" ]] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[[ -z "$root" ]] && exit 0

git -C "$root" status --porcelain -- frontend 2>/dev/null |
  grep -qE '\.(ts|tsx)$|package\.json$' || exit 0

# Binaries hoist to the workspace root. Skip quietly when deps are not installed,
# so a fresh clone does not fail every turn.
bin="$root/node_modules/.bin"
[[ -x "$bin/knip" && -x "$bin/tsr" ]] || exit 0

# The route tree has to be current, or every route file looks unreachable.
(cd "$root/frontend" && "$bin/tsr" generate) >/dev/null 2>&1

output=$(cd "$root/frontend" && "$bin/knip" --no-progress 2>&1)
if [[ $? -ne 0 ]]; then
  {
    echo "Knip found unused code — delete it before finishing, or justify an ignore in frontend/knip.config.ts:"
    head -40 <<<"$output"
  } >&2
  exit 2
fi

exit 0
