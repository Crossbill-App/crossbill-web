#!/bin/bash
# Stop hook: report copy-paste duplication introduced by this turn.
# Two signals, both worth acting on before the turn ends:
#   1. a clone whose duplicated lines overlap lines this turn changed — the
#      copy-paste you just made, caught while the context is still loaded;
#   2. the ratchet threshold in .jscpd.json being passed, which is exactly what
#      CI fails on.
# Only (2) is enforced by CI; (1) is the cheap early warning. Pre-existing
# clones in files you happened to touch stay quiet — the overlap test is
# against changed *lines*, not changed files.
# Costs ~30ms per stack, and only fires when that stack's sources are dirty.

input=$(cat)

# Claude Code sets this when the stop was already blocked once — bail so we can't loop.
[[ "$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null)" == "true" ]] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[[ -z "$root" ]] && exit 0

# The binary hoists to the workspace root. Skip quietly when deps are not
# installed, so a fresh clone does not fail every turn.
bin="$root/node_modules/.bin/jscpd"
[[ -x "$bin" ]] || exit 0

tmp=$(mktemp -d) || exit 0
trap 'rm -rf "$tmp"' EXIT

report=""

# Line ranges this turn touched, as {"<repo-relative path>": [[start, end], ...]}.
# Hunk headers give the post-image line numbers, which is what jscpd sees in the
# working tree. Untracked files count whole.
changed_lines() {
  local stack=$1
  {
    git -C "$root" diff -U0 --no-color HEAD -- "$stack" 2>/dev/null | awk '
      /^\+\+\+ b\// { file = substr($0, 7); next }
      /^@@/ {
        match($0, /\+[0-9]+(,[0-9]+)?/)
        split(substr($0, RSTART + 1, RLENGTH - 1), h, ",")
        count = (h[2] == "" ? 1 : h[2])
        if (count > 0) print file "\t" h[1] "\t" h[1] + count - 1
      }'
    git -C "$root" ls-files --others --exclude-standard -- "$stack" 2>/dev/null |
      awk '{ print $0 "\t1\t999999999" }'
  } | jq -R -s '
    split("\n") | map(select(length > 0) | split("\t"))
    | group_by(.[0])
    | map({key: .[0][0], value: map([(.[1] | tonumber), (.[2] | tonumber)])})
    | from_entries'
}

check_stack() {
  local stack=$1 pattern=$2
  git -C "$root" status --porcelain -- "$stack" 2>/dev/null |
    grep -qE "$pattern" || return 0

  # Must run from the stack directory: that is where its .jscpd.json lives.
  local out status
  out=$(cd "$root/$stack" && "$bin" --no-tips --absolute --reporters json,threshold \
    --output "$tmp/$stack" 2>&1) && status=0 || status=$?

  local json="$tmp/$stack/jscpd-report.json" clones=""
  [[ -f "$json" ]] && clones=$(jq -r \
    --argjson changed "$(changed_lines "$stack")" --arg root "$root/" '
    def overlaps($f; $path): ($changed[$path] // [])
      | any(.[0] <= $f.end and .[1] >= $f.start);
    .duplicates[]
    | .firstFile as $a | .secondFile as $b
    | ($a.name | ltrimstr($root)) as $ap
    | ($b.name | ltrimstr($root)) as $bp
    | select(overlaps($a; $ap) or overlaps($b; $bp))
    | "  \($ap):\($a.start)-\($a.end) ~ \($bp):\($b.start)-\($b.end) (\(.lines) lines)"
  ' "$json")

  if [[ -n "$clones" ]]; then
    report+="Code changed this turn duplicates code that already exists:"$'\n'
    report+="$clones"$'\n'
  fi

  # Non-zero means the ratchet in $stack/.jscpd.json was passed — CI fails on this.
  if [[ $status -ne 0 ]]; then
    report+="$(grep -F 'ERROR:' <<<"$out") ($stack/.jscpd.json)"$'\n'
  fi
}

check_stack backend '\.py$'
check_stack frontend '\.(ts|tsx)$'

if [[ -n "$report" ]]; then
  {
    printf '%s' "$report"
    echo "Extract the shared code into a helper both sides call. Never raise the"
    echo "threshold to make the check pass — it is a ratchet (see CLAUDE.md >"
    echo "Duplication). If the duplication is deliberate and extracting it would"
    echo "make the code worse, say why and finish the turn."
  } >&2
  exit 2
fi

exit 0
