#!/usr/bin/env bash
set -euo pipefail

TARGET_TAG="${1:-}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/ubuntu/CampusHub}"

cd "$DEPLOY_DIR"

if [ -z "$TARGET_TAG" ]; then
  if [ ! -f .env.release.previous ]; then
    echo "No previous release recorded. Pass a release tag explicitly." >&2
    exit 66
  fi
  TARGET_TAG="$(sed -n 's/^CAMPUSHUB_IMAGE_TAG=//p' .env.release.previous | tail -n 1)"
fi

if [ -z "$TARGET_TAG" ]; then
  echo "Rollback target tag is empty." >&2
  exit 64
fi

for image in campushub-agent campushub-backend campushub-web; do
  if ! sudo docker image inspect "$image:$TARGET_TAG" >/dev/null 2>&1; then
    echo "Missing rollback image: $image:$TARGET_TAG" >&2
    exit 66
  fi
done

CURRENT_TAG=""
if [ -f .env.release ]; then
  CURRENT_TAG="$(sed -n 's/^CAMPUSHUB_IMAGE_TAG=//p' .env.release | tail -n 1)"
fi

if [ -n "$CURRENT_TAG" ] && [ "$CURRENT_TAG" != "$TARGET_TAG" ]; then
  printf 'CAMPUSHUB_IMAGE_TAG=%s\n' "$CURRENT_TAG" > .env.release.previous
fi

printf 'CAMPUSHUB_IMAGE_TAG=%s\n' "$TARGET_TAG" > .env.release

echo "Rolling CampusHub back to $TARGET_TAG"
sudo env CAMPUSHUB_IMAGE_TAG="$TARGET_TAG" \
  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-build

sudo env CAMPUSHUB_IMAGE_TAG="$TARGET_TAG" \
  docker compose -f docker-compose.prod.yml --env-file .env.prod ps

if [ -x scripts/server/smoke-test.sh ]; then
  scripts/server/smoke-test.sh "http://127.0.0.1"
fi

echo "Rollback to $TARGET_TAG completed."
