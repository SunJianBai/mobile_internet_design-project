#!/usr/bin/env bash
set -euo pipefail

RELEASE_TAG="${1:-}"
BUNDLE_PATH="${2:-}"
PUBLIC_BASE_URL="${3:-${PUBLIC_BASE_URL:-https://sun227454.online/CampusHub}}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/ubuntu/CampusHub}"
PUBLIC_BASE_PATH="$(printf '%s' "$PUBLIC_BASE_URL" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]*##; s#/*$##')"
LOCAL_SMOKE_BASE_URL="http://127.0.0.1${PUBLIC_BASE_PATH}"

if [ -z "$RELEASE_TAG" ]; then
  echo "Usage: scripts/server/deploy-release.sh <release-tag> <image-bundle> [public-base-url]" >&2
  exit 64
fi

if [ -z "$BUNDLE_PATH" ]; then
  BUNDLE_PATH="$DEPLOY_DIR/releases/campushub-images-$RELEASE_TAG.tar"
fi

if [ ! -f "$BUNDLE_PATH" ]; then
  echo "Image bundle not found: $BUNDLE_PATH" >&2
  exit 66
fi

cd "$DEPLOY_DIR"
mkdir -p releases backups

CURRENT_TAG=""
if [ -f .env.release ]; then
  CURRENT_TAG="$(sed -n 's/^CAMPUSHUB_IMAGE_TAG=//p' .env.release | tail -n 1)"
fi

if [ -n "$CURRENT_TAG" ] && [ "$CURRENT_TAG" != "$RELEASE_TAG" ]; then
  printf 'CAMPUSHUB_IMAGE_TAG=%s\n' "$CURRENT_TAG" > .env.release.previous
  printf 'CAMPUSHUB_PREVIOUS_IMAGE_TAG=%s\n' "$CURRENT_TAG" > "backups/previous-before-$RELEASE_TAG.env"
fi

echo "Loading Docker images from $BUNDLE_PATH"
sudo docker load -i "$BUNDLE_PATH"

printf 'CAMPUSHUB_IMAGE_TAG=%s\n' "$RELEASE_TAG" > .env.release

echo "Starting CampusHub release $RELEASE_TAG"
sudo env CAMPUSHUB_IMAGE_TAG="$RELEASE_TAG" \
  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build

sudo env CAMPUSHUB_IMAGE_TAG="$RELEASE_TAG" \
  docker compose -f docker-compose.prod.yml --env-file .env.prod ps

if [ -x scripts/server/smoke-test.sh ]; then
  scripts/server/smoke-test.sh "$LOCAL_SMOKE_BASE_URL"
fi

echo "Release $RELEASE_TAG deployed successfully."
