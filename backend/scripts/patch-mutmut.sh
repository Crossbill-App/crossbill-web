#!/usr/bin/env bash
# Usage: ./scripts/patch-mutmut.sh   (run from backend/)
# Patches the installed mutmut so that `src` being a real package works.
#
# mutmut 3 assumes `src/` is a src-layout source root and strips the leading
# `src.` from module names. Here `src` IS a real package (we import
# `src.domain.*`), so the stripped name never matches the imported module: the
# mutant trampoline is never armed and every single mutant falsely "survives".
#
# Re-run after any `uv sync`/`uv add` that reinstalls mutmut. Idempotent.
set -euo pipefail

MARKER="patched by scripts/patch-mutmut.sh"
REPLACEMENT="    pass  # ${MARKER}: src is a real package here"

MUTMUT_DIR=$(uv run python -c "import mutmut, pathlib; print(pathlib.Path(mutmut.__file__).parent)")
MUTMUT_VERSION=$(uv run python -c "from importlib.metadata import version; print(version('mutmut'))")
FORMAT_UTILS="$MUTMUT_DIR/utils/format_utils.py"
MAIN="$MUTMUT_DIR/__main__.py"

echo "==> Patching mutmut in $MUTMUT_DIR"

# sed -i is not portable (GNU vs BSD), so write via a sibling temp file.
patch_line() {
  file="$1"
  pattern="$2"
  tmp="$file.patch-mutmut.tmp"
  sed "s|$pattern|$REPLACEMENT|" "$file" >"$tmp"
  mv "$tmp" "$file"
}

patch_line "$FORMAT_UTILS" '^    module_name = strip_prefix(module_name, prefix="src\.")$'
patch_line "$MAIN" '^    assert not name\.startswith("src\.").*$'

failed=0
for file in "$FORMAT_UTILS" "$MAIN"; do
  if grep -q "$MARKER" "$file"; then
    echo "    ok: $file"
  else
    echo "    MISSING PATCH: $file" >&2
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  cat >&2 <<EOF

Failed to patch mutmut: the expected source lines were not found, most likely
because mutmut changed upstream (installed version: ${MUTMUT_VERSION}).
Do NOT trust a mutation run until this is fixed - without the patch no mutant
is ever activated and the whole suite reports a false 100% survival rate.
EOF
  exit 1
fi

echo "==> mutmut patched."
