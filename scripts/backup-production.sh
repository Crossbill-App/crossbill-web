#!/bin/bash
# Back up Railway production into a single zip archive on this machine. Read
# only: nothing in production is written to, and no local database is touched.
#
# The archive holds a custom-format pg_dump and the book files, so it restores
# with `pg_restore` plus an `aws s3 sync` of the extracted book-files directory.
#
# EPUBs are left out by default — they are the bulk of the bytes and can be
# re-uploaded from their sources, while book covers are generated and small.
# Pass --with-epubs for a complete copy.
#
# Production discovery, its requirements (RAILWAY_API_TOKEN,
# RAILWAY_ENVIRONMENT_ID) and the overrides that bypass it live in
# scripts/lib/railway-production.sh. `make backup-production` sources those from
# the git-ignored root .env.deploy, the same file `make deploy` uses, so no extra
# setup is needed. Needs pg_dump, psql, jq, curl, zip, and aws.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: backup-production.sh [options]

  -o, --output PATH  Where to write the archive. A directory (or a path that
                     does not end in .zip) keeps the generated filename.
                     Default: backups/crossbill-production-<UTC timestamp>.zip
      --with-epubs   Include the EPUB files as well as the book covers.
      --no-files     Back up the database only, leaving out book files entirely.
      --with-jobs    Include the SAQ job-queue rows (schema only by default).
  -f, --force        Overwrite an existing archive at that path.
  -h, --help         Show this help.
EOF
}

OUTPUT=""
WITH_EPUBS=false
BACKUP_FILES=true
WITH_JOBS=false
FORCE=false

while [ $# -gt 0 ]; do
  case "$1" in
    -o | --output)
      [ $# -ge 2 ] || {
        echo "--output needs a path." >&2
        exit 2
      }
      OUTPUT="$2"
      shift
      ;;
    --with-epubs) WITH_EPUBS=true ;;
    --no-files) BACKUP_FILES=false ;;
    --with-jobs) WITH_JOBS=true ;;
    -f | --force) FORCE=true ;;
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

# shellcheck source=lib/railway-production.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/railway-production.sh"

require_tools jq curl zip pg_dump psql
[ "$BACKUP_FILES" = true ] && require_tools aws

# --- Where the archive goes --------------------------------------------------

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE_NAME="crossbill-production-${TIMESTAMP}.zip"

case "$OUTPUT" in
  '') ARCHIVE="${REPO_ROOT}/backups/${ARCHIVE_NAME}" ;;
  *.zip) ARCHIVE="$OUTPUT" ;;
  *) ARCHIVE="${OUTPUT%/}/${ARCHIVE_NAME}" ;;
esac

if [ -e "$ARCHIVE" ] && [ "$FORCE" = false ]; then
  echo "${ARCHIVE} already exists. Pass --force to overwrite it." >&2
  exit 1
fi

mkdir -p "$(dirname "$ARCHIVE")"
# zip writes relative to the staging directory, so resolve the path first.
ARCHIVE="$(cd "$(dirname "$ARCHIVE")" && pwd)/$(basename "$ARCHIVE")"

# --- Resolve the production side ---------------------------------------------

resolve_production_database_url
[ "$BACKUP_FILES" = true ] && resolve_production_s3 --no-files

require_pg_dump_at_least_server "$PRODUCTION_DATABASE_URL"

echo
echo "  database  $(redact "$PRODUCTION_DATABASE_URL")"
if [ "$BACKUP_FILES" = true ]; then
  echo "  files     ${PRODUCTION_S3_ENDPOINT_URL}/${PRODUCTION_S3_BUCKET_NAME}"
fi
echo "         -> ${ARCHIVE}"
echo

STAGING_DIR="$(mktemp -d -t crossbill-backup-XXXXXX)"
trap 'rm -rf "$STAGING_DIR"' EXIT

# --- Database ----------------------------------------------------------------

DUMP_ARGS=(--format=custom --no-owner --no-privileges)
if [ "$WITH_JOBS" = false ]; then
  # The queue is transient state, and restoring a backlog would have a worker
  # re-run jobs that already finished, some of which cost money.
  DUMP_ARGS+=(--exclude-table-data 'public.saq_jobs' --exclude-table-data 'public.saq_stats')
fi

echo "Dumping production..."
pg_dump "${DUMP_ARGS[@]}" --file "${STAGING_DIR}/database.dump" "$PRODUCTION_DATABASE_URL"
echo "Dumped $(du -h "${STAGING_DIR}/database.dump" | cut -f1)."

# --- Book files --------------------------------------------------------------

FILE_COUNT=0
if [ "$BACKUP_FILES" = true ]; then
  SYNC_ARGS=(--only-show-errors)
  if [ "$WITH_EPUBS" = false ]; then
    # Excluding the prefix rather than syncing book-covers/ alone, so any key
    # prefix added later still lands in the backup.
    SYNC_ARGS+=(--exclude 'epubs/*')
  fi

  echo "Downloading book files..."
  mkdir -p "${STAGING_DIR}/book-files"
  aws_prod s3 sync "s3://${PRODUCTION_S3_BUCKET_NAME}" "${STAGING_DIR}/book-files" "${SYNC_ARGS[@]}"
  FILE_COUNT="$(find "${STAGING_DIR}/book-files" -type f | wc -l | tr -d ' ')"
  echo "Downloaded ${FILE_COUNT} files."
fi

# --- Manifest ----------------------------------------------------------------

SERVER_VERSION="$(psql "$PRODUCTION_DATABASE_URL" -tAc 'SHOW server_version')"
ALEMBIC_REVISION="$(psql "$PRODUCTION_DATABASE_URL" -tAc 'SELECT version_num FROM alembic_version' 2>/dev/null || echo unknown)"

cat >"${STAGING_DIR}/MANIFEST.txt" <<EOF
Crossbill production backup
created         ${TIMESTAMP} UTC
source          $(redact "$PRODUCTION_DATABASE_URL")
postgres        ${SERVER_VERSION}
alembic head    ${ALEMBIC_REVISION}
job queue rows  $([ "$WITH_JOBS" = true ] && echo included || echo "excluded (schema only)")
book files      $(
  if [ "$BACKUP_FILES" = false ]; then
    echo "excluded"
  elif [ "$WITH_EPUBS" = true ]; then
    echo "${FILE_COUNT} files, EPUBs included"
  else
    echo "${FILE_COUNT} files, EPUBs excluded"
  fi
)

Restore the database into an empty database:
  pg_restore --dbname "\$DATABASE_URL" --no-owner --no-privileges --single-transaction database.dump

Restore the book files into object storage:
  aws --endpoint-url "\$S3_ENDPOINT_URL" s3 sync book-files "s3://\$S3_BUCKET_NAME"
EOF

# --- Archive -----------------------------------------------------------------

echo "Writing the archive..."
rm -f "$ARCHIVE"
(cd "$STAGING_DIR" && zip -q -r "$ARCHIVE" .)

echo
echo "Wrote ${ARCHIVE} ($(du -h "$ARCHIVE" | cut -f1))."
if [ "$BACKUP_FILES" = true ] && [ "$WITH_EPUBS" = false ]; then
  echo "EPUB files were left out; pass --with-epubs to include them."
fi
