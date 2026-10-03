#!/usr/bin/env bash
# One-time setup for the Garage S3-compatible storage container.
# Prerequisites: docker compose up -d garage
set -euo pipefail

CONTAINER="crossbill-garage"
BUCKET="crossbill-files"
KEY_NAME="crossbill-key"

echo "==> Getting node ID..."
NODE_ID=$(docker exec "$CONTAINER" /garage node id -q | cut -c1-16)
echo "    Node ID: $NODE_ID"

echo "==> Assigning storage layout..."
docker exec "$CONTAINER" /garage layout assign -z dc1 -c 1G "$NODE_ID"
docker exec "$CONTAINER" /garage layout apply --version 1

echo "==> Creating bucket '$BUCKET'..."
docker exec "$CONTAINER" /garage bucket create "$BUCKET"

echo "==> Creating API key '$KEY_NAME'..."
docker exec "$CONTAINER" /garage key create "$KEY_NAME"

echo "==> Granting read/write/owner access..."
docker exec "$CONTAINER" /garage bucket allow --read --write --owner "$BUCKET" --key "$KEY_NAME"

echo ""
echo "Done! Add these to the .env in the repository root:"
echo "  S3_ENDPOINT_URL=http://garage:3900      # backend in Docker (docker-compose.yml)"
echo "  S3_ENDPOINT_URL=http://localhost:3900   # backend on your machine (development)"
echo "  S3_ACCESS_KEY_ID=<Key ID from above>"
echo "  S3_SECRET_ACCESS_KEY=<Secret key from above>"
echo "  S3_BUCKET_NAME=$BUCKET"
echo "  S3_REGION=garage"
echo ""
echo "Then apply them with: docker compose up -d"
