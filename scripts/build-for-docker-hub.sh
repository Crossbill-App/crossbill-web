#!/bin/bash
# Usage: ./build-for-docker-hub.sh [UNIQUE_TAG]
# Builds and pushes a nightly image to Docker Hub under a unique tag.
# Stable releases should be done by CI.
#
# The moving :nightly tag is refreshed only for builds of main, so that
# deploying a feature branch (see railway-deploy.sh) cannot repoint the tag
# other people pull. MOVE_NIGHTLY=1/0 overrides; when unset it is inferred from
# the checked-out branch, so callers on a detached HEAD must set it explicitly.
#
# Requires `docker buildx` (BuildKit). Bundled with Docker Engine 23+ on Linux.
# On macOS with the Homebrew docker CLI (no Docker Desktop):
#   brew install docker-buildx
#   mkdir -p ~/.docker/cli-plugins
#   ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" \
#     ~/.docker/cli-plugins/docker-buildx

set -e # Exit on error

# Optional first arg pins the unique tag (so callers can deploy that exact image).
UNIQUE_TAG="${1:-nightly-$(date +%Y%m%d%H%M%S)}"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
MOVE_NIGHTLY="${MOVE_NIGHTLY:-$([ "$BRANCH" = "main" ] && echo 1 || echo 0)}"

TAGS=(-t "tumetsu/crossbill:${UNIQUE_TAG}")
if [ "$MOVE_NIGHTLY" = "1" ]; then
  TAGS+=(-t tumetsu/crossbill:nightly)
fi

echo "Building and pushing ${UNIQUE_TAG}..."

docker buildx build \
  --platform linux/amd64 \
  "${TAGS[@]}" \
  -f ./Dockerfile \
  --push \
  .

if [ "$MOVE_NIGHTLY" = "1" ]; then
  echo "Pushed tags: nightly, ${UNIQUE_TAG}"
else
  echo "Pushed tag: ${UNIQUE_TAG}"
fi
