#!/bin/bash
# Shared discovery of the Railway production endpoints, sourced by
# clone-production-db.sh and backup-production.sh. Not executable on its own.
#
# Requirements (no `railway` CLI / login needed — talks to the API directly):
#   - RAILWAY_API_TOKEN   Account/Team token: railway.com -> Account -> Tokens.
#                         NOTE: must be this name, NOT RAILWAY_TOKEN (the CLI
#                         reserves RAILWAY_TOKEN for project tokens and will
#                         reject an account token placed there).
#   - RAILWAY_ENVIRONMENT_ID   which environment to read. Resource ID (not kept
#                         in-repo). Find it with `railway status --json`.
#
# Both production endpoints are discovered through the Railway API rather than
# being configured here, so no resource IDs live in the repo. The database is
# whichever one the app actually connects to: the service holding DATABASE_URL
# without PGDATA is the app, and the Postgres service whose private domain that
# URL names is production. Anything keyed off variable names alone — "the service
# exposing DATABASE_PUBLIC_URL" — silently picks a retired database once a project
# holds two of them, which is what happened when production moved to pgvector.
# Object storage still comes from the service exposing S3_BUCKET_NAME.
# Pin either with RAILWAY_POSTGRES_SERVICE_ID / RAILWAY_SERVICE_ID, or bypass
# discovery with PRODUCTION_DATABASE_URL and the PRODUCTION_S3_* variables.

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${LIB_DIR}/../.." && pwd)"
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

# Sets FOUND_VARS / FOUND_SERVICE to the one service that uses a database
# without being one: it holds DATABASE_URL but no PGDATA, which every Railway
# Postgres image sets. That is the app, and what it points at defines production.
find_database_consumer() {
  local i matches=() names=()
  discover_services
  for i in "${!SERVICE_NAMES[@]}"; do
    echo "${SERVICE_VARS[$i]}" | jq -e '.DATABASE_URL and (.PGDATA | not)' >/dev/null 2>&1 &&
      matches+=("$i")
  done

  case "${#matches[@]}" in
    1)
      FOUND_SERVICE="${SERVICE_NAMES[${matches[0]}]}"
      FOUND_VARS="${SERVICE_VARS[${matches[0]}]}"
      ;;
    0)
      echo "No service in this Railway environment connects to a database." >&2
      return 1
      ;;
    *)
      for i in "${matches[@]}"; do names+=("${SERVICE_NAMES[$i]}"); done
      echo "Several services connect to a database: ${names[*]}" >&2
      echo "Pin the app with RAILWAY_SERVICE_ID, or set PRODUCTION_DATABASE_URL." >&2
      return 1
      ;;
  esac
}

# Sets FOUND_VARS / FOUND_SERVICE to the service whose private domain is $1.
find_service_by_private_domain() {
  local domain="$1" i
  discover_services
  for i in "${!SERVICE_NAMES[@]}"; do
    [ "$(echo "${SERVICE_VARS[$i]}" | jq -r '.RAILWAY_PRIVATE_DOMAIN // empty')" = "$domain" ] || continue
    FOUND_SERVICE="${SERVICE_NAMES[$i]}"
    FOUND_VARS="${SERVICE_VARS[$i]}"
    return 0
  done
  return 1
}

# Echoes the hostname of a connection URL.
url_host() {
  local authority="${1#*://}"
  authority="${authority%%/*}"
  authority="${authority##*@}"
  echo "${authority%%:*}"
}

# Echoes a URL for the database service whose variables are $1 that resolves from
# outside Railway, or nothing if it only publishes a private endpoint. A service
# without a TCP proxy still sets DATABASE_URL, pointing at .railway.internal,
# which is unreachable here and would fail much later as a DNS error.
public_database_url() {
  local vars="$1" url
  url="$(echo "$vars" | jq -r '.DATABASE_PUBLIC_URL // empty')"
  [ -n "$url" ] || url="$(echo "$vars" | jq -r '.DATABASE_URL // empty')"
  case "$(url_host "$url")" in
    '' | *.railway.internal) return 0 ;;
  esac
  printf '%s' "$url"
}

# Strips the userinfo from a connection URL so it can be printed safely.
redact() {
  echo "$1" | sed -E 's#(://)[^/@]*@#\1<credentials>@#'
}

# Reads one key out of the root .env. Sourcing the whole file is not safe — not
# all of its values are shell-quoted.
env_value() {
  [ -f "${REPO_ROOT}/.env" ] || return 0
  sed -n "s/^$1=//p" "${REPO_ROOT}/.env" | tail -n 1 | sed -E 's/^["'"'"']//; s/["'"'"']$//'
}

# Sets PRODUCTION_DATABASE_URL, unless it is already set in the environment.
resolve_production_database_url() {
  if [ -n "${PRODUCTION_DATABASE_URL:-}" ]; then
    echo "Using PRODUCTION_DATABASE_URL from the environment."
    return 0
  fi

  if [ -n "${RAILWAY_POSTGRES_SERVICE_ID:-}" ]; then
    discover_services
    PRODUCTION_DATABASE_URL="$(public_database_url "$(service_variables "$RAILWAY_POSTGRES_SERVICE_ID")")"
    [ -n "$PRODUCTION_DATABASE_URL" ] || {
      echo "Service ${RAILWAY_POSTGRES_SERVICE_ID} publishes no endpoint reachable from here." >&2
      echo "Enable its public TCP proxy in the Railway dashboard, or set PRODUCTION_DATABASE_URL." >&2
      exit 1
    }
    return 0
  fi

  echo "Resolving the production database from Railway..."
  find_database_consumer || exit 1
  local app_service app_db_host
  app_service="$FOUND_SERVICE"
  app_db_host="$(url_host "$(echo "$FOUND_VARS" | jq -r '.DATABASE_URL')")"

  find_service_by_private_domain "$app_db_host" || {
    echo "The '${app_service}' service points at ${app_db_host}, which is not a service" >&2
    echo "in this environment. Pin RAILWAY_POSTGRES_SERVICE_ID, or set PRODUCTION_DATABASE_URL." >&2
    exit 1
  }

  PRODUCTION_DATABASE_URL="$(public_database_url "$FOUND_VARS")"
  [ -n "$PRODUCTION_DATABASE_URL" ] || {
    echo "The '${FOUND_SERVICE}' database publishes no endpoint reachable from here." >&2
    echo "Enable its public TCP proxy in the Railway dashboard, or set PRODUCTION_DATABASE_URL." >&2
    exit 1
  }
  echo "Found the '${FOUND_SERVICE}' database, which '${app_service}' connects to."
}

# Sets the PRODUCTION_S3_* variables, unless they are already set in the
# environment. $1 is the flag to suggest when production has no S3 storage.
resolve_production_s3() {
  local no_files_flag="${1:---no-files}"

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
    echo "Pass ${no_files_flag} if production keeps book files on a container volume." >&2
    exit 1
  fi
}

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

# Fails early when the local pg_dump cannot read the server at $1: pg_dump
# refuses a server newer than itself, and the error it gives is easy to misread
# as a connection problem.
require_pg_dump_at_least_server() {
  local remote_major dump_major
  remote_major="$(psql "$1" -tAc 'SHOW server_version_num' | cut -c1-2)"
  dump_major="$(pg_dump --version | sed -E 's/.* ([0-9]+).*/\1/')"
  if [ "$dump_major" -lt "$remote_major" ]; then
    echo "pg_dump is version ${dump_major} but production runs PostgreSQL ${remote_major}." >&2
    echo "Install PostgreSQL ${remote_major} client tools or newer." >&2
    exit 1
  fi
}
