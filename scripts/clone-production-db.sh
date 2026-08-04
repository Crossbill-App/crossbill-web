#!/bin/bash
# Replace the local development database with a clone of the Railway production
# database. Destructive by design: the local database is dropped and recreated.
#
# Requirements (no `railway` CLI / login needed — talks to the API directly):
#   - RAILWAY_API_TOKEN   Account/Team token: railway.com -> Account -> Tokens.
#                         NOTE: must be this name, NOT RAILWAY_TOKEN (the CLI
#                         reserves RAILWAY_TOKEN for project tokens and will
#                         reject an account token placed there).
#   - RAILWAY_ENVIRONMENT_ID   which environment to clone from. Resource ID (not
#                         kept in-repo). Find it with `railway status --json`.
#   - pg_dump / pg_restore / psql, jq, curl
#
# `make clone-production-db` sources these from the git-ignored root .env.deploy,
# the same file `make deploy` uses, so no extra setup is needed.
#
# The Postgres service is discovered automatically: the script lists the
# environment's services and picks the one exposing DATABASE_PUBLIC_URL. Pin it
# with RAILWAY_POSTGRES_SERVICE_ID if the project ever grows a second database.
# Set PRODUCTION_DATABASE_URL to bypass Railway discovery entirely.
#
# The local target comes from LOCAL_DATABASE_URL, else DATABASE_URL in the root
# .env, else the dev default. It must point at localhost — cloning over a remote
# database is refused unless you pass --force.
#
# Only the database is cloned. Book files and covers live in object storage and
# are untouched, so rows may reference files the local S3 bucket does not have.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: clone-production-db.sh [options]

  -y, --yes         Skip the confirmation prompt.
      --force       Allow a target that is not on localhost.
      --no-migrate  Skip `alembic upgrade head` after restoring.
      --with-jobs   Also copy the SAQ job-queue rows (skipped by default so the
                    local worker does not re-run production's queued jobs).
  -h, --help        Show this help.
EOF
}

ASSUME_YES=false
FORCE=false
MIGRATE=true
WITH_JOBS=false

while [ $# -gt 0 ]; do
  case "$1" in
    -y | --yes) ASSUME_YES=true ;;
    --force) FORCE=true ;;
    --no-migrate) MIGRATE=false ;;
    --with-jobs) WITH_JOBS=true ;;
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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API="https://backboard.railway.com/graphql/v2"

for tool in pg_dump pg_restore psql; do
  command -v "$tool" >/dev/null || {
    echo "Missing ${tool}. Install the PostgreSQL client tools." >&2
    exit 1
  }
done

gql() {
  # $1 = full JSON request body; echoes the response, fails on a GraphQL error.
  local resp
  resp="$(curl -sS -X POST "$API" \
    -H "Authorization: Bearer ${RAILWAY_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$1")"
  if echo "$resp" | jq -e '.errors' >/dev/null 2>&1; then
    echo "Railway API error: $resp" >&2
    exit 1
  fi
  printf '%s' "$resp"
}

service_variables() {
  # $1 = service id; echoes that service instance's resolved variables as JSON.
  gql "$(jq -n --arg p "$PROJECT_ID" --arg e "$ENVIRONMENT_ID" --arg s "$1" '{
    query: "query($p: String!, $e: String!, $s: String!) { variables(projectId: $p, environmentId: $e, serviceId: $s) }",
    variables: { p: $p, e: $e, s: $s }
  }')" | jq '.data.variables'
}

resolve_production_url() {
  : "${RAILWAY_API_TOKEN:?Set RAILWAY_API_TOKEN (railway.com -> Account -> Tokens; NOT RAILWAY_TOKEN), or set PRODUCTION_DATABASE_URL}"
  ENVIRONMENT_ID="${RAILWAY_ENVIRONMENT_ID:?Set RAILWAY_ENVIRONMENT_ID (find it with: railway status --json)}"
  command -v jq >/dev/null || {
    echo "Missing jq." >&2
    exit 1
  }

  PROJECT_ID="$(gql "$(jq -n --arg id "$ENVIRONMENT_ID" '{
    query: "query($id: String!) { environment(id: $id) { projectId } }",
    variables: { id: $id }
  }')" | jq -r '.data.environment.projectId')"

  if [ -n "${RAILWAY_POSTGRES_SERVICE_ID:-}" ]; then
    local url
    url="$(service_variables "$RAILWAY_POSTGRES_SERVICE_ID" | jq -r '.DATABASE_PUBLIC_URL // empty')"
    [ -n "$url" ] || {
      echo "Service ${RAILWAY_POSTGRES_SERVICE_ID} exposes no DATABASE_PUBLIC_URL." >&2
      echo "Enable its public TCP proxy in the Railway dashboard, or set PRODUCTION_DATABASE_URL." >&2
      exit 1
    }
    PRODUCTION_DATABASE_URL="$url"
    return
  fi

  # No pinned service: take the one service in the environment that publishes a
  # DATABASE_PUBLIC_URL. Anything other than exactly one is ambiguous.
  local services matches=() id name url
  services="$(gql "$(jq -n --arg id "$PROJECT_ID" '{
    query: "query($id: String!) { project(id: $id) { services { edges { node { id name } } } } }",
    variables: { id: $id }
  }')" | jq -r '.data.project.services.edges[].node | "\(.id) \(.name)"')"

  while read -r id name; do
    [ -n "$id" ] || continue
    url="$(service_variables "$id" | jq -r '.DATABASE_PUBLIC_URL // empty')"
    [ -n "$url" ] && matches+=("${name}"$'\t'"${url}")
  done <<<"$services"

  case "${#matches[@]}" in
    1)
      PRODUCTION_SERVICE_NAME="${matches[0]%%$'\t'*}"
      PRODUCTION_DATABASE_URL="${matches[0]#*$'\t'}"
      ;;
    0)
      echo "No service in this Railway environment exposes DATABASE_PUBLIC_URL." >&2
      echo "Enable the database's public TCP proxy, or set PRODUCTION_DATABASE_URL." >&2
      exit 1
      ;;
    *)
      echo "Several services expose a database URL: ${matches[*]%%$'\t'*}" >&2
      echo "Pin one with RAILWAY_POSTGRES_SERVICE_ID." >&2
      exit 1
      ;;
  esac
}

# Strips the userinfo from a connection URL so it can be printed safely.
redact() {
  echo "$1" | sed -E 's#(://)[^/@]*@#\1<credentials>@#'
}

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

local_database_url() {
  if [ -n "${LOCAL_DATABASE_URL:-}" ]; then
    echo "$LOCAL_DATABASE_URL"
    return
  fi
  # Read only the one key rather than sourcing .env, whose other values are not
  # all shell-safe.
  local from_env=""
  [ -f "${REPO_ROOT}/.env" ] &&
    from_env="$(sed -n 's/^DATABASE_URL=//p' "${REPO_ROOT}/.env" | tail -n 1 | sed -E 's/^["'"'"']//; s/["'"'"']$//')"
  echo "${from_env:-postgresql://crossbill:crossbill_dev_password@localhost:5432/crossbill}"
}

# --- Resolve both ends -------------------------------------------------------

if [ -n "${PRODUCTION_DATABASE_URL:-}" ]; then
  echo "Using PRODUCTION_DATABASE_URL from the environment."
else
  echo "Resolving the production database from Railway..."
  resolve_production_url
  echo "Found the '${PRODUCTION_SERVICE_NAME:-postgres}' service."
fi

LOCAL_URL="$(local_database_url)"
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

# pg_dump refuses to read a server newer than itself, and the error it gives is
# easy to misread as a connection problem.
REMOTE_MAJOR="$(psql "$PRODUCTION_DATABASE_URL" -tAc 'SHOW server_version_num' | cut -c1-2)"
DUMP_MAJOR="$(pg_dump --version | sed -E 's/.* ([0-9]+).*/\1/')"
if [ "$DUMP_MAJOR" -lt "$REMOTE_MAJOR" ]; then
  echo "pg_dump is version ${DUMP_MAJOR} but production runs PostgreSQL ${REMOTE_MAJOR}." >&2
  echo "Install PostgreSQL ${REMOTE_MAJOR} client tools or newer." >&2
  exit 1
fi

# --- Confirm -----------------------------------------------------------------

echo
echo "  from  $(redact "$PRODUCTION_DATABASE_URL")"
echo "  into  $(redact "$LOCAL_URL")"
echo
echo "This DROPS the local '${LOCAL_DB}' database and everything in it."

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

# --- Dump --------------------------------------------------------------------

DUMP_FILE="$(mktemp -t crossbill-production-XXXXXX.dump)"
cleanup() { rm -f "$DUMP_FILE"; }
trap cleanup EXIT

DUMP_ARGS=(--format=custom --no-owner --no-privileges)
if [ "$WITH_JOBS" = false ]; then
  # Schema only for the queue tables: a cloned backlog would have the local
  # worker re-running production's jobs, some of which cost money.
  DUMP_ARGS+=(--exclude-table-data 'public.saq_jobs' --exclude-table-data 'public.saq_stats')
fi

echo "Dumping production..."
pg_dump "${DUMP_ARGS[@]}" --file "$DUMP_FILE" "$PRODUCTION_DATABASE_URL"
echo "Dumped $(du -h "$DUMP_FILE" | cut -f1)."

# --- Restore -----------------------------------------------------------------

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

echo
echo "Local database now mirrors production."
if [ "$WITH_JOBS" = false ]; then
  echo "The SAQ job queue was left empty; pass --with-jobs to copy it too."
fi
echo "Book files were not copied — rows may reference objects your local storage lacks."
