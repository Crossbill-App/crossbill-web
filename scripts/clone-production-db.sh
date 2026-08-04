#!/bin/bash
# Replace the local development database and book files with a clone of Railway
# production. Destructive by design: the local database is dropped and
# recreated, and local book storage is mirrored onto production's.
#
# Requirements (no `railway` CLI / login needed — talks to the API directly):
#   - RAILWAY_API_TOKEN   Account/Team token: railway.com -> Account -> Tokens.
#                         NOTE: must be this name, NOT RAILWAY_TOKEN (the CLI
#                         reserves RAILWAY_TOKEN for project tokens and will
#                         reject an account token placed there).
#   - RAILWAY_ENVIRONMENT_ID   which environment to clone from. Resource ID (not
#                         kept in-repo). Find it with `railway status --json`.
#   - pg_dump / pg_restore / psql, jq, curl, and aws (for book files)
#
# `make clone-production-db` sources these from the git-ignored root .env.deploy,
# the same file `make deploy` uses, so no extra setup is needed.
#
# Both production endpoints are discovered through the Railway API rather than
# being configured here, so no resource IDs live in the repo: the database is the
# service exposing DATABASE_PUBLIC_URL, and object storage comes from the service
# exposing S3_BUCKET_NAME. Pin either with RAILWAY_POSTGRES_SERVICE_ID /
# RAILWAY_SERVICE_ID, or bypass discovery with PRODUCTION_DATABASE_URL and the
# PRODUCTION_S3_* variables.
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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API="https://backboard.railway.com/graphql/v2"

require_tools() {
  local tool
  for tool in "$@"; do
    command -v "$tool" >/dev/null || {
      echo "Missing ${tool}." >&2
      exit 1
    }
  done
}

require_tools jq curl
[ "$CLONE_DB" = true ] && require_tools pg_dump pg_restore psql
[ "$CLONE_FILES" = true ] && require_tools aws

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

# Loads every service's variables into SERVICE_NAMES / SERVICE_VARS once, so the
# database and the storage credentials cost one discovery pass between them.
declare -a SERVICE_NAMES=()
declare -a SERVICE_VARS=()
DISCOVERED=false

discover_services() {
  [ "$DISCOVERED" = true ] && return
  : "${RAILWAY_API_TOKEN:?Set RAILWAY_API_TOKEN (railway.com -> Account -> Tokens; NOT RAILWAY_TOKEN)}"
  ENVIRONMENT_ID="${RAILWAY_ENVIRONMENT_ID:?Set RAILWAY_ENVIRONMENT_ID (find it with: railway status --json)}"

  PROJECT_ID="$(gql "$(jq -n --arg id "$ENVIRONMENT_ID" '{
    query: "query($id: String!) { environment(id: $id) { projectId } }",
    variables: { id: $id }
  }')" | jq -r '.data.environment.projectId')"

  local services id name
  services="$(gql "$(jq -n --arg id "$PROJECT_ID" '{
    query: "query($id: String!) { project(id: $id) { services { edges { node { id name } } } } }",
    variables: { id: $id }
  }')" | jq -r '.data.project.services.edges[].node | "\(.id) \(.name)"')"

  while read -r id name; do
    [ -n "$id" ] || continue
    SERVICE_NAMES+=("$name")
    SERVICE_VARS+=("$(service_variables "$id")")
  done <<<"$services"

  DISCOVERED=true
}

# Finds the one service whose variables contain $1, and sets FOUND_VARS /
# FOUND_SERVICE. Anything other than exactly one match is ambiguous.
find_service_by_variable() {
  local key="$1" i matches=()
  discover_services
  for i in "${!SERVICE_NAMES[@]}"; do
    echo "${SERVICE_VARS[$i]}" | jq -e --arg k "$key" '.[$k] // empty' >/dev/null 2>&1 &&
      matches+=("$i")
  done

  case "${#matches[@]}" in
    1)
      FOUND_SERVICE="${SERVICE_NAMES[${matches[0]}]}"
      FOUND_VARS="${SERVICE_VARS[${matches[0]}]}"
      ;;
    0)
      echo "No service in this Railway environment exposes ${key}." >&2
      return 1
      ;;
    *)
      local names=()
      for i in "${matches[@]}"; do names+=("${SERVICE_NAMES[$i]}"); done
      echo "Several services expose ${key}: ${names[*]}" >&2
      return 1
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

# Reads one key out of the root .env. Sourcing the whole file is not safe — not
# all of its values are shell-quoted.
env_value() {
  [ -f "${REPO_ROOT}/.env" ] || return 0
  sed -n "s/^$1=//p" "${REPO_ROOT}/.env" | tail -n 1 | sed -E 's/^["'"'"']//; s/["'"'"']$//'
}

# --- Resolve the production side ---------------------------------------------

if [ "$CLONE_DB" = true ]; then
  if [ -n "${PRODUCTION_DATABASE_URL:-}" ]; then
    echo "Using PRODUCTION_DATABASE_URL from the environment."
  elif [ -n "${RAILWAY_POSTGRES_SERVICE_ID:-}" ]; then
    discover_services
    PRODUCTION_DATABASE_URL="$(service_variables "$RAILWAY_POSTGRES_SERVICE_ID" | jq -r '.DATABASE_PUBLIC_URL // empty')"
    [ -n "$PRODUCTION_DATABASE_URL" ] || {
      echo "Service ${RAILWAY_POSTGRES_SERVICE_ID} exposes no DATABASE_PUBLIC_URL." >&2
      echo "Enable its public TCP proxy in the Railway dashboard, or set PRODUCTION_DATABASE_URL." >&2
      exit 1
    }
  else
    echo "Resolving the production database from Railway..."
    find_service_by_variable DATABASE_PUBLIC_URL || {
      echo "Enable the database's public TCP proxy, pin RAILWAY_POSTGRES_SERVICE_ID, or set PRODUCTION_DATABASE_URL." >&2
      exit 1
    }
    PRODUCTION_DATABASE_URL="$(echo "$FOUND_VARS" | jq -r '.DATABASE_PUBLIC_URL')"
    echo "Found the '${FOUND_SERVICE}' service."
  fi
fi

if [ "$CLONE_FILES" = true ]; then
  if [ -n "${PRODUCTION_S3_BUCKET_NAME:-}" ]; then
    echo "Using PRODUCTION_S3_* from the environment."
  else
    if [ -n "${RAILWAY_SERVICE_ID:-}" ]; then
      discover_services
      FOUND_VARS="$(service_variables "$RAILWAY_SERVICE_ID")"
    else
      echo "Resolving production object storage from Railway..."
      find_service_by_variable S3_BUCKET_NAME || {
        echo "Pin the app service with RAILWAY_SERVICE_ID, or set the PRODUCTION_S3_* variables." >&2
        exit 1
      }
      echo "Found the '${FOUND_SERVICE}' service."
    fi
    PRODUCTION_S3_BUCKET_NAME="$(echo "$FOUND_VARS" | jq -r '.S3_BUCKET_NAME // empty')"
    PRODUCTION_S3_ENDPOINT_URL="$(echo "$FOUND_VARS" | jq -r '.S3_ENDPOINT_URL // empty')"
    PRODUCTION_S3_ACCESS_KEY_ID="$(echo "$FOUND_VARS" | jq -r '.S3_ACCESS_KEY_ID // empty')"
    PRODUCTION_S3_SECRET_ACCESS_KEY="$(echo "$FOUND_VARS" | jq -r '.S3_SECRET_ACCESS_KEY // empty')"
    PRODUCTION_S3_REGION="$(echo "$FOUND_VARS" | jq -r '.S3_REGION // "us-east-1"')"
  fi

  if [ -z "${PRODUCTION_S3_BUCKET_NAME:-}" ] || [ -z "${PRODUCTION_S3_ACCESS_KEY_ID:-}" ]; then
    echo "Production has no S3 storage configured; nothing to copy." >&2
    echo "Pass --no-files if production keeps book files on a container volume." >&2
    exit 1
  fi
fi

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

  # pg_dump refuses to read a server newer than itself, and the error it gives is
  # easy to misread as a connection problem.
  REMOTE_MAJOR="$(psql "$PRODUCTION_DATABASE_URL" -tAc 'SHOW server_version_num' | cut -c1-2)"
  DUMP_MAJOR="$(pg_dump --version | sed -E 's/.* ([0-9]+).*/\1/')"
  if [ "$DUMP_MAJOR" -lt "$REMOTE_MAJOR" ]; then
    echo "pg_dump is version ${DUMP_MAJOR} but production runs PostgreSQL ${REMOTE_MAJOR}." >&2
    echo "Install PostgreSQL ${REMOTE_MAJOR} client tools or newer." >&2
    exit 1
  fi
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

# Runs the aws CLI with one endpoint's credentials, isolated from any ambient
# AWS_PROFILE / SSO session that would otherwise take precedence.
aws_with() {
  local key="$1" secret="$2" region="$3" endpoint="$4"
  shift 4
  env -u AWS_PROFILE -u AWS_SESSION_TOKEN -u AWS_DEFAULT_PROFILE \
    AWS_ACCESS_KEY_ID="$key" AWS_SECRET_ACCESS_KEY="$secret" AWS_DEFAULT_REGION="$region" \
    aws --endpoint-url "$endpoint" "$@"
}

aws_prod() {
  aws_with "$PRODUCTION_S3_ACCESS_KEY_ID" "$PRODUCTION_S3_SECRET_ACCESS_KEY" \
    "$PRODUCTION_S3_REGION" "$PRODUCTION_S3_ENDPOINT_URL" "$@"
}

aws_local() {
  aws_with "$LOCAL_S3_ACCESS_KEY_ID" "$LOCAL_S3_SECRET_ACCESS_KEY" \
    "$LOCAL_S3_REGION" "$LOCAL_S3_ENDPOINT_URL" "$@"
}

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
