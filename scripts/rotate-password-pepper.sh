#!/bin/bash
# Replace production's PASSWORD_PEPPER and set a new password for one account in
# the same step. Every stored hash includes the pepper, so any other account with
# a password can no longer log in afterwards; the script refuses to run while
# such accounts exist unless you pass --force.
#
# Needs RAILWAY_API_TOKEN, RAILWAY_ENVIRONMENT_ID and RAILWAY_SERVICE_ID (the
# app) from the git-ignored root .env.deploy, plus psql, jq, curl and uv.
# The new password is read from the terminal and never leaves this machine; only
# its Argon2 hash is written to the database.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: rotate-password-pepper.sh [options]

  --email EMAIL  The account to set the new password for. Defaults to the only
                 account that has a password.
  --force        Run even though other accounts with passwords will be locked out.
  -y, --yes      Skip the confirmation prompt.
  -h, --help     Show this help.
EOF
}

EMAIL=""
FORCE=false
ASSUME_YES=false

while [ $# -gt 0 ]; do
  case "$1" in
    --email)
      EMAIL="${2:?--email needs a value}"
      shift
      ;;
    --force) FORCE=true ;;
    -y | --yes) ASSUME_YES=true ;;
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

require_tools psql jq curl uv
SERVICE_ID="${RAILWAY_SERVICE_ID:?Set RAILWAY_SERVICE_ID to the app service (find it with: railway status --json)}"

resolve_production_database_url
DB="$PRODUCTION_DATABASE_URL"

sql() {
  psql "$DB" -X -v ON_ERROR_STOP=1 -Atq "$@"
}

if [ -z "$EMAIL" ]; then
  mapfile -t accounts < <(sql -c "SELECT email FROM users WHERE hashed_password IS NOT NULL")
  if [ "${#accounts[@]}" -ne 1 ]; then
    echo "${#accounts[@]} accounts have a password; pass --email to pick one." >&2
    exit 1
  fi
  EMAIL="${accounts[0]}"
fi

[ "$(sql -v email="$EMAIL" <<<"SELECT count(*) FROM users WHERE email = :'email'")" = 1 ] || {
  echo "No account with email ${EMAIL}." >&2
  exit 1
}

others="$(sql -v email="$EMAIL" <<<"SELECT count(*) FROM users WHERE hashed_password IS NOT NULL AND email <> :'email'")"
if [ "$others" -gt 0 ] && [ "$FORCE" = false ]; then
  echo "${others} other account(s) have a password and could no longer log in." >&2
  echo "Pass --force to rotate anyway; they would need their password set again." >&2
  exit 1
fi

echo
echo "Production database: $(redact "$DB")"
echo "Account:             ${EMAIL}"
echo "Logins fail from the database update until the redeploy finishes (about a minute)."
if [ "$ASSUME_YES" = false ]; then
  read -r -p "Rotate the pepper and set a new password? [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]] || exit 1
fi

read -r -s -p "New password: " PASSWORD
echo
read -r -s -p "Repeat it: " repeat
echo
[ "$PASSWORD" = "$repeat" ] || {
  echo "The passwords differ." >&2
  exit 1
}
[ "${#PASSWORD}" -ge 8 ] || {
  echo "Use at least 8 characters, the app's own minimum." >&2
  exit 1
}

PEPPER="$(openssl rand -base64 48 | tr -d '\n')"

# Passed through the environment so neither secret shows up in `ps`.
HASH="$(cd "${REPO_ROOT}/backend" && PASSWORD="$PASSWORD" PEPPER="$PEPPER" uv run --quiet python -c '
import os
from pwdlib import PasswordHash
print(PasswordHash.recommended().hash(os.environ["PASSWORD"] + os.environ["PEPPER"]))
')"
unset PASSWORD repeat

sql -v email="$EMAIL" -v hash="$HASH" <<<"UPDATE users SET hashed_password = :'hash', updated_at = now() WHERE email = :'email'"
echo "Stored the new password hash."

# From here the database only matches the new pepper, so a failure must not lose it.
on_failure() {
  echo >&2
  echo "Failed after the database update. Set PASSWORD_PEPPER on the app service to" >&2
  echo "the value below and redeploy, or nobody can log in:" >&2
  echo "$PEPPER" >&2
}
trap on_failure ERR

PROJECT_ID="$(gql "$(jq -n --arg id "$RAILWAY_ENVIRONMENT_ID" '{
  query: "query($id: String!) { environment(id: $id) { projectId } }",
  variables: { id: $id }
}')" | jq -r '.data.environment.projectId')"

gql "$(jq -n --arg p "$PROJECT_ID" --arg e "$RAILWAY_ENVIRONMENT_ID" --arg s "$SERVICE_ID" --arg v "$PEPPER" '{
  query: "mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }",
  variables: { input: { projectId: $p, environmentId: $e, serviceId: $s, name: "PASSWORD_PEPPER", value: $v, skipDeploys: true } }
}')" >/dev/null
echo "Set PASSWORD_PEPPER on the app service."

DEPLOYMENT_ID="$(gql "$(jq -n --arg s "$SERVICE_ID" --arg e "$RAILWAY_ENVIRONMENT_ID" '{
  query: "mutation($serviceId: String!, $environmentId: String!) { serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId) }",
  variables: { serviceId: $s, environmentId: $e }
}')" | jq -r '.data.serviceInstanceDeployV2')"
trap - ERR

# A deployment reports SUCCESS even when its container crash-loops, so wait for
# uvicorn's own startup line instead.
echo "Waiting for deployment ${DEPLOYMENT_ID} to start serving..."
for _ in $(seq 1 60); do
  started="$(gql "$(jq -n --arg id "$DEPLOYMENT_ID" '{
    query: "query($id: String!) { deploymentLogs(deploymentId: $id, filter: \"Application startup complete\", limit: 1) { message } }",
    variables: { id: $id }
  }')" | jq '.data.deploymentLogs | length')"
  if [ "$started" -gt 0 ]; then
    echo "The app is up with the new pepper. Log in as ${EMAIL} with the new password,"
    echo "then update the password in the KOReader plugin."
    exit 0
  fi
  sleep 5
done

echo "The app has not logged its startup after 5 minutes; check deployment ${DEPLOYMENT_ID}." >&2
exit 1
