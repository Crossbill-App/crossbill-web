#!/usr/bin/env bash
# Auto-check files after Edit/Write operations
# Called by Claude Code hooks with $CLAUDE_FILE_PATHS

set -euo pipefail

PROJECT_ROOT="/home/tuomas/Code/crossbill/crossbill-web"

python_checked=0

for file in $CLAUDE_FILE_PATHS; do
    # Skip if file doesn't exist
    [[ -f "$file" ]] || continue

    case "$file" in
        *.py)
            echo "━━━ Checking Python: $file ━━━"
            python_checked=1

            # Run ruff (formatter) - keeps files matching CI's `ruff format --check`
            cd "$PROJECT_ROOT/backend" && uv run ruff format "$file" 2>&1 | head -5

            # Run ruff (linter)
            if cd "$PROJECT_ROOT/backend" && uv run ruff check "$file" 2>&1 | head -20; then
                echo "✓ Ruff: no issues"
            fi

            # Run pyright (type checker) - only show errors
            echo "Running pyright..."
            cd "$PROJECT_ROOT/backend"
            if output=$(uv run pyright "$file" --outputjson 2>/dev/null); then
                error_count=$(echo "$output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    errors = [d for d in data.get('generalDiagnostics', []) if d.get('severity') == 'error']
    print(len(errors))
except:
    print('0')
")
                if [[ "$error_count" -eq 0 ]]; then
                    echo "✓ Pyright: no type errors"
                else
                    echo "⚠ Pyright: $error_count type errors"
                    echo "$output" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    errors = [d for d in data.get('generalDiagnostics', []) if d.get('severity') == 'error']
    for d in errors[:5]:  # Show first 5 errors
        line = d['range']['start']['line'] + 1
        char = d['range']['start']['character']
        msg = d['message']
        print(f\"  {line}:{char} - {msg}\")
    if len(errors) > 5:
        print(f\"  ... and {len(errors) - 5} more errors\")
except Exception as e:
    print(f\"  (Could not parse pyright output: {e})\")
"
                fi
            else
                echo "  (pyright check skipped)"
            fi
            ;;

        *.ts|*.tsx)
            echo "━━━ Checking TypeScript: $file ━━━"

            # Run eslint
            if cd "$PROJECT_ROOT/frontend" && npm run lint -- "$file" 2>&1 | head -15; then
                echo "✓ ESLint: no issues"
            fi

            # TypeScript type checking is done project-wide, skip for individual files
            echo "  (Note: Run 'npm run type-check' manually for full TypeScript validation)"
            ;;

        *)
            # Skip other file types
            ;;
    esac
done

# Import-linter works on the whole import graph, so run it once per invocation
if [[ "$python_checked" -eq 1 ]]; then
    echo "Running import-linter..."
    if output=$(cd "$PROJECT_ROOT/backend" && uv run lint-imports 2>&1); then
        echo "✓ Import-linter: all contracts kept"
    else
        echo "⚠ Import-linter: broken contracts"
        echo "$output" | sed -n '/Broken contracts/,$p' | head -40
    fi
fi
