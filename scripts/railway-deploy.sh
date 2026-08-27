#!/bin/bash
# Build+push a nightly image and deploy it to Railway on-demand.
#
# Why not `railway redeploy`? Railway caches a floating tag's digest for hours and
# redeploy reuses the existing deployment's image reference, so it will NOT pick up
# a freshly-pushed :nightly. Instead we push a uniquely-tagged image and point the
# service at it via the GraphQL API, which forces an immediate deploy of the new
# digest. You never copy a tag by hand; the pinned tag also gives clean rollbacks.
#
# Requirements (no `railway` CLI / login needed — talks to the API directly):
#   - RAILWAY_API_TOKEN   Account/Team token: railway.com -> Account -> Tokens.
#                         NOTE: must be this name, NOT RAILWAY_TOKEN (the CLI
#                         reserves RAILWAY_TOKEN for project tokens and will
#                         reject an account token placed there).
#   - RAILWAY_SERVICE_ID / RAILWAY_ENVIRONMENT_ID   which service+env to deploy.
#                         Resource IDs (not kept in-repo). Find them once with
#                         `railway status --json` and export alongside the token.
#   - docker buildx, jq, curl
#
# Optional:
#   - DEPLOY_REF            Ref being deployed; defaults to the checked-out
#                           branch. Set it when HEAD is detached (CI), since it
#                           names the image tag and decides whether the moving
#                           :nightly tag moves.
#   - RAILWAY_DEPLOY_DEBUG  Dump raw API responses on error. Off by default: the
#                           responses carry project and service names, and this
#                           also runs in CI logs.
set -euo pipefail

: "${RAILWAY_API_TOKEN:?Set RAILWAY_API_TOKEN (railway.com -> Account -> Tokens; NOT RAILWAY_TOKEN)}"

SERVICE_ID="${RAILWAY_SERVICE_ID:?Set RAILWAY_SERVICE_ID (find it with: railway status --json)}"
ENVIRONMENT_ID="${RAILWAY_ENVIRONMENT_ID:?Set RAILWAY_ENVIRONMENT_ID (find it with: railway status --json)}"
API="https://backboard.railway.com/graphql/v2"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Any ref can be deployed, so the tag records which one: a bare timestamp cannot
# tell a main deploy from a branch one, and the tag is what Railway shows as live.
REF_NAME="${DEPLOY_REF:-$(git rev-parse --abbrev-ref HEAD)}"
SHORT_SHA="$(git rev-parse --short HEAD)"
# Docker tags allow [A-Za-z0-9_.-] only and must not start with . or -, so refs
# like `feat/thing` need slugging.
REF_SLUG="$(printf '%s' "$REF_NAME" | tr '[:upper:]' '[:lower:]' |
  sed -e 's#[^a-z0-9._-]#-#g' -e 's#^[^a-z0-9_]*##' | cut -c1-40)"
[ -n "$REF_SLUG" ] || REF_SLUG="ref"
# The timestamp stays: redeploying the same commit must still produce an image
# reference Railway has not seen, or it serves the cached digest.
TAG="${REF_SLUG}-${SHORT_SHA}-$(date +%Y%m%d%H%M%S)"
IMAGE="tumetsu/crossbill:${TAG}"

echo "Deploying ${REF_NAME} (${SHORT_SHA}) as ${IMAGE}"

# 1. Build & push the pinned tag (:nightly moves only for main; see the build script).
MOVE_NIGHTLY="$([ "$REF_NAME" = "main" ] && echo 1 || echo 0)" \
  "${SCRIPT_DIR}/build-for-docker-hub.sh" "$TAG"

gql() {
  # $1 = full JSON request body; echoes the response, fails on a GraphQL error.
  local resp
  resp="$(curl -sS -X POST "$API" \
    -H "Authorization: Bearer ${RAILWAY_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$1")"
  if echo "$resp" | jq -e '.errors' >/dev/null 2>&1; then
    # Only the GraphQL messages: the full body can name the project, service and
    # domain, and this runs somewhere the log outlives the deploy.
    echo "Railway API error: $(echo "$resp" | jq -c '[.errors[].message]' 2>/dev/null || echo '[unparseable response]')" >&2
    if [ -n "${RAILWAY_DEPLOY_DEBUG:-}" ]; then echo "$resp" >&2; fi
    exit 1
  fi
  printf '%s' "$resp"
}

echo "Pointing Railway service at ${IMAGE} and deploying..."

# 2. Update the service's source image to the freshly-pushed tag.
gql "$(jq -n --arg svc "$SERVICE_ID" --arg env "$ENVIRONMENT_ID" --arg image "$IMAGE" '{
  query: "mutation($serviceId: String!, $environmentId: String, $input: ServiceInstanceUpdateInput!) { serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input) }",
  variables: { serviceId: $svc, environmentId: $env, input: { source: { image: $image } } }
}')" >/dev/null

# 3. Deploy the updated source.
#
# NOT serviceInstanceRedeploy: it re-runs the *existing deployment's* image and
# ignores the source we just updated, so it silently keeps an old image live
# forever (it pinned this service to a 6-day-old build without ever failing).
# serviceInstanceDeployV2 creates a new deployment from the current source.
gql "$(jq -n --arg svc "$SERVICE_ID" --arg env "$ENVIRONMENT_ID" '{
  query: "mutation($serviceId: String!, $environmentId: String!) { serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId) }",
  variables: { serviceId: $svc, environmentId: $env }
}')" >/dev/null

# 4. Confirm the deployment that actually went live is running OUR image.
# Without this the whole script can succeed while deploying something else.
echo "Waiting for Railway to report a deployment of ${IMAGE}..."
for _ in $(seq 1 60); do
  resp="$(gql "$(jq -n --arg svc "$SERVICE_ID" --arg env "$ENVIRONMENT_ID" '{
    query: "query($serviceId: String!, $environmentId: String!) { serviceInstance(serviceId: $serviceId, environmentId: $environmentId) { latestDeployment { status meta } } }",
    variables: { serviceId: $svc, environmentId: $env }
  }')")"
  status="$(echo "$resp" | jq -r '.data.serviceInstance.latestDeployment.status // "UNKNOWN"')"
  live="$(echo "$resp" | jq -r '.data.serviceInstance.latestDeployment.meta.image // "unknown"')"

  # The previous deployment stays "latest" for a moment after the trigger, so a
  # mismatch here is only conclusive once we give up below.
  if [ "$live" = "$IMAGE" ]; then
    case "$status" in
      SUCCESS)
        echo "Deployed ${IMAGE} to Railway."
        exit 0
        ;;
      FAILED | CRASHED)
        echo "Deployment of ${IMAGE} ended as ${status}." >&2
        exit 1
        ;;
    esac
  fi
  sleep 5
done

echo "Timed out waiting for ${IMAGE}; Railway's latest deployment is ${live} (${status})." >&2
exit 1
