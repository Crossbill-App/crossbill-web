#!/bin/bash
# Stop hook: type-check the frontend once per turn.
# tsc checks the whole program, so a per-edit run (alongside format-all.sh,
# which runs pyright per file for the backend) would cost the full check on
# every edit. Incremental build info keeps a warm run at ~2s against ~12s cold.
# Only fires when frontend sources are dirty. CI runs `npm run type-check`.

input=$(cat)

# Claude Code sets this when the stop was already blocked once — bail so we can't loop.
[[ "$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null)" == "true" ]] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[[ -z "$root" ]] && exit 0

git -C "$root" status --porcelain -- frontend 2>/dev/null | grep -qE '\.(ts|tsx)$' || exit 0

# Binaries hoist to the workspace root. Skip quietly when deps are not installed,
# so a fresh clone does not fail every turn.
bin="$root/node_modules/.bin"
[[ -x "$bin/tsc" && -x "$bin/tsr" ]] || exit 0

# A new or renamed route only type-checks against a regenerated route tree.
(cd "$root/frontend" && "$bin/tsr" generate) >/dev/null 2>&1

output=$(cd "$root/frontend" && "$bin/tsc" --noEmit --incremental \
  --tsBuildInfoFile "$root/node_modules/.cache/crossbill-frontend.tsbuildinfo" 2>&1)
if [[ $? -ne 0 ]]; then
  {
    echo "Frontend type errors — fix these before finishing:"
    grep -E 'error TS' <<<"$output" | head -40
  } >&2
  exit 2
fi

exit 0
