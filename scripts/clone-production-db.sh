#!/bin/bash
# Replace the local development database and book files with a clone of Railway
# production. Destructive by design: the local database is dropped and
# recreated, and local book storage is mirrored onto production's.
#
# Production discovery, its requirements (RAILWAY_API_TOKEN,
# RAILWAY_ENVIRONMENT_ID) and the overrides that bypass it live in
# scripts/lib/railway-production.sh. `make clone-production-db` sources those
# from the git-ignored root .env.deploy, the same file `make deploy` uses, so no
# extra setup is needed. Needs pg_dump / pg_restore / psql, jq, curl, and aws.
#
# The local database comes from LOCAL_DATABASE_URL, else DATABASE_URL in the root
# .env, else the dev default. It must point at localhost — cloning over a remote
# database is refused unless you pass --force.
#
# Local book files go to the S3_* bucket from the root .env (Garage, normally),
# or to backend/book-files when S3 is not configured, matching how the app itself
# picks a storage backend.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: clone-production-db.sh [options]

  -y, --yes         Skip the confirmation prompt.
      --force       Allow a target that is not on localhost.
      --no-migrate  Skip `alembic upgrade head` after restoring.
      --with-jobs   Also copy the SAQ job-queue rows (skipped by default so the
                    local worker does not re-run production's queued jobs).
      --no-files    Clone the database only, leaving book files alone.
      --files-only  Clone book files only, leaving the database alone.
  -h, --help        Show this help.
EOF
}

ASSUME_YES=false
FORCE=false
MIGRATE=true
WITH_JOBS=false
CLONE_DB=true
CLONE_FILES=true

while [ $# -gt 0 ]; do
  case "$1" in
    -y | --yes) ASSUME_YES=true ;;
    --force) FORCE=true ;;
    --no-migrate) MIGRATE=false ;;
    --with-jobs) WITH_JOBS=true ;;
    --no-files) CLONE_FILES=false ;;
    --files-only) CLONE_DB=false ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ "$CLONE_DB" = false ] && [ "$CLONE_FILES" = false ]; then
  echo "--no-files and --files-only leave nothing to do." >&2
  exit 2
fi

# shellcheck source=lib/railway-production.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/railway-production.sh"

require_tools jq curl
[ "$CLONE_DB" = true ] && require_tools pg_dump pg_restore psql
[ "$CLONE_FILES" = true ] && require_tools aws

# Splits a connection URL into HOST, DB_NAME and MAINTENANCE_URL (the same
# server with the `postgres` database), so we can drop the target database
# without being connected to it.
parse_url() {
  local url="$1" authority hostport query
  [[ "$url" =~ ^postgres(ql)?://([^/?]+)/([^?]+)(\?.*)?$ ]] || {
    echo "Cannot parse connection URL: $(redact "$url")" >&2
    echo "Expected postgresql://user:password@host:port/database" >&2
    exit 1
  }
  authority="${BASH_REMATCH[2]}"
  DB_NAME="${BASH_REMATCH[3]}"
  query="${BASH_REMATCH[4]}"
  hostport="${authority##*@}"
  HOST="${hostport%%:*}"
  MAINTENANCE_URL="postgresql://${authority}/postgres${query}"
}

aws_local() {
  aws_with "$LOCAL_S3_ACCESS_KEY_ID" "$LOCAL_S3_SECRET_ACCESS_KEY" \
    "$LOCAL_S3_REGION" "$LOCAL_S3_ENDPOINT_URL" "$@"
}

# --- Resolve the production side ---------------------------------------------

[ "$CLONE_DB" = true ] && resolve_production_database_url
[ "$CLONE_FILES" = true ] && resolve_production_s3 --no-files

# --- Resolve the local side --------------------------------------------------

if [ "$CLONE_DB" = true ]; then
  LOCAL_URL="${LOCAL_DATABASE_URL:-$(env_value DATABASE_URL)}"
  LOCAL_URL="${LOCAL_URL:-postgresql://crossbill:crossbill_dev_password@localhost:5432/crossbill}"
  parse_url "$LOCAL_URL"
  LOCAL_HOST="$HOST"
  LOCAL_DB="$DB_NAME"
  LOCAL_MAINTENANCE_URL="$MAINTENANCE_URL"

  case "$LOCAL_HOST" in
    localhost | 127.0.0.1 | ::1 | '[::1]') ;;
    *)
      if [ "$FORCE" = false ]; then
        echo "Refusing to overwrite ${LOCAL_DB} on '${LOCAL_HOST}', which is not localhost." >&2
        echo "Pass --force if you really mean to clone into that database." >&2
        exit 1
      fi
      echo "WARNING: target host '${LOCAL_HOST}' is not localhost (--force given)."
      ;;
  esac

  psql "$LOCAL_MAINTENANCE_URL" -tAc 'SELECT 1' >/dev/null 2>&1 || {
    echo "Cannot reach the local PostgreSQL server at ${LOCAL_HOST}." >&2
    echo "Start it with: docker compose -f docker-compose.dev.yml up -d postgres" >&2
    exit 1
  }

  require_pg_dump_at_least_server "$PRODUCTION_DATABASE_URL"
fi

if [ "$CLONE_FILES" = true ]; then
  LOCAL_S3_BUCKET_NAME="${LOCAL_S3_BUCKET_NAME:-$(env_value S3_BUCKET_NAME)}"
  LOCAL_S3_ENDPOINT_URL="${LOCAL_S3_ENDPOINT_URL:-$(env_value S3_ENDPOINT_URL)}"
  LOCAL_S3_ACCESS_KEY_ID="${LOCAL_S3_ACCESS_KEY_ID:-$(env_value S3_ACCESS_KEY_ID)}"
  LOCAL_S3_SECRET_ACCESS_KEY="${LOCAL_S3_SECRET_ACCESS_KEY:-$(env_value S3_SECRET_ACCESS_KEY)}"
  LOCAL_S3_REGION="${LOCAL_S3_REGION:-$(env_value S3_REGION)}"
  LOCAL_S3_REGION="${LOCAL_S3_REGION:-us-east-1}"

  # config.py falls back to the filesystem unless all four are present, so mirror
  # that decision here instead of assuming Garage is running.
  if [ -n "$LOCAL_S3_BUCKET_NAME" ] && [ -n "$LOCAL_S3_ENDPOINT_URL" ] &&
    [ -n "$LOCAL_S3_ACCESS_KEY_ID" ] && [ -n "$LOCAL_S3_SECRET_ACCESS_KEY" ]; then
    FILES_TARGET="s3://${LOCAL_S3_BUCKET_NAME}"
    FILES_TARGET_LABEL="${LOCAL_S3_ENDPOINT_URL}/${LOCAL_S3_BUCKET_NAME}"
  else
    # The S3 key prefixes (epubs/, book-covers/) are exactly the subdirectories
    # config.py expects under book-files, so a plain sync lands them correctly.
    FILES_TARGET="${REPO_ROOT}/backend/book-files"
    FILES_TARGET_LABEL="$FILES_TARGET (S3 not configured in .env)"
  fi
fi

# --- Confirm -----------------------------------------------------------------

echo
if [ "$CLONE_DB" = true ]; then
  echo "  database  $(redact "$PRODUCTION_DATABASE_URL")"
  echo "         -> $(redact "$LOCAL_URL")"
fi
if [ "$CLONE_FILES" = true ]; then
  echo "  files     ${PRODUCTION_S3_ENDPOINT_URL}/${PRODUCTION_S3_BUCKET_NAME}"
  echo "         -> ${FILES_TARGET_LABEL}"
fi
echo
[ "$CLONE_DB" = true ] && echo "This DROPS the local '${LOCAL_DB}' database and everything in it."
[ "$CLONE_FILES" = true ] && echo "Local book files not present in production will be deleted."

if [ "$ASSUME_YES" = false ]; then
  if [ -r /dev/tty ]; then
    read -r -p "Continue? [y/N] " reply </dev/tty
  else
    echo "Not running interactively; pass --yes to confirm." >&2
    exit 1
  fi
  case "$reply" in
    y | Y | yes | YES) ;;
    *)
      echo "Aborted."
      exit 1
      ;;
  esac
fi

# --- Database ----------------------------------------------------------------

if [ "$CLONE_DB" = true ]; then
  DUMP_FILE="$(mktemp -t crossbill-production-XXXXXX.dump)"
  trap 'rm -f "$DUMP_FILE"' EXIT

  DUMP_ARGS=(--format=custom --no-owner --no-privileges)
  if [ "$WITH_JOBS" = false ]; then
    # Schema only for the queue tables: a cloned backlog would have the local
    # worker re-running production's jobs, some of which cost money.
    DUMP_ARGS+=(--exclude-table-data 'public.saq_jobs' --exclude-table-data 'public.saq_stats')
  fi

  echo "Dumping production..."
  pg_dump "${DUMP_ARGS[@]}" --file "$DUMP_FILE" "$PRODUCTION_DATABASE_URL"
  echo "Dumped $(du -h "$DUMP_FILE" | cut -f1)."

  echo "Recreating the local '${LOCAL_DB}' database..."
  psql "$LOCAL_MAINTENANCE_URL" -v ON_ERROR_STOP=1 -q \
    -c "DROP DATABASE IF EXISTS \"${LOCAL_DB}\" WITH (FORCE)" \
    -c "CREATE DATABASE \"${LOCAL_DB}\""

  echo "Restoring..."
  pg_restore --dbname "$LOCAL_URL" --no-owner --no-privileges --single-transaction "$DUMP_FILE"

  if [ "$MIGRATE" = true ]; then
    # Production usually trails the working branch, so bring the clone up to the
    # migrations this checkout expects.
    echo "Applying migrations..."
    (cd "${REPO_ROOT}/backend" && DATABASE_URL="$LOCAL_URL" uv run alembic upgrade head)
  fi
fi

# --- Book files --------------------------------------------------------------

if [ "$CLONE_FILES" = true ]; then
  case "$FILES_TARGET" in
    s3://*)
      aws_local s3 ls "$FILES_TARGET" >/dev/null 2>&1 || {
        echo "Cannot reach the local bucket ${FILES_TARGET_LABEL}." >&2
        echo "Start Garage with: docker compose -f docker-compose.dev.yml up -d garage" >&2
        echo "If the bucket does not exist yet, create it with: ./scripts/setup_garage.sh" >&2
        exit 1
      }
      # The aws CLI cannot sync between two endpoints in one call, so stage the
      # objects locally and push them on. Production's bucket is never written to.
      STAGING_DIR="$(mktemp -d -t crossbill-book-files-XXXXXX)"
      trap 'rm -f "${DUMP_FILE:-}"; rm -rf "$STAGING_DIR"' EXIT

      echo "Downloading book files from production..."
      aws_prod s3 sync "s3://${PRODUCTION_S3_BUCKET_NAME}" "$STAGING_DIR" --only-show-errors
      echo "Uploading to ${FILES_TARGET_LABEL}..."
      aws_local s3 sync "$STAGING_DIR" "$FILES_TARGET" --delete --only-show-errors
      FILE_COUNT="$(find "$STAGING_DIR" -type f | wc -l)"
      ;;
    *)
      echo "Downloading book files to ${FILES_TARGET}..."
      mkdir -p "$FILES_TARGET"
      aws_prod s3 sync "s3://${PRODUCTION_S3_BUCKET_NAME}" "$FILES_TARGET" --delete --only-show-errors
      FILE_COUNT="$(find "$FILES_TARGET" -type f | wc -l)"
      ;;
  esac
  echo "Synced ${FILE_COUNT} book files."
fi

# --- Done --------------------------------------------------------------------

echo
if [ "$CLONE_DB" = true ] && [ "$CLONE_FILES" = true ]; then
  echo "Local database and book files now mirror production."
elif [ "$CLONE_DB" = true ]; then
  echo "Local database now mirrors production."
else
  echo "Local book files now mirror production."
fi
if [ "$CLONE_DB" = true ] && [ "$WITH_JOBS" = false ]; then
  echo "The SAQ job queue was left empty; pass --with-jobs to copy it too."
fi
