#!/usr/bin/env bash
set -euo pipefail

TARGET_TAG="${1:-}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/ubuntu/CampusHub}"
PUBLIC_BASE_PATH="${PUBLIC_BASE_PATH:-/CampusHub}"
LOCAL_SMOKE_BASE_URL="${LOCAL_SMOKE_BASE_URL:-}"

cd "$DEPLOY_DIR"

resolve_local_smoke_base_url() {
  if [ -n "$LOCAL_SMOKE_BASE_URL" ]; then
    printf '%s\n' "$LOCAL_SMOKE_BASE_URL"
    return
  fi

  local bind host port origin
  bind="${FRONTEND_HTTP_PORT:-}"
  if [ -z "$bind" ] && [ -f .env.prod ]; then
    bind="$(sed -n 's/^FRONTEND_HTTP_PORT=//p' .env.prod | tail -n 1 | tr -d '\r')"
  fi
  bind="${bind:-127.0.0.1:18080}"
  bind="${bind%\"}"
  bind="${bind#\"}"
  bind="${bind%\'}"
  bind="${bind#\'}"

  case "$bind" in
    *:*)
      host="${bind%:*}"
      port="${bind##*:}"
      if [ -z "$host" ] || [ "$host" = "0.0.0.0" ]; then
        host="127.0.0.1"
      fi
      origin="http://$host:$port"
      ;;
    *)
      origin="http://127.0.0.1:$bind"
      ;;
  esac

  printf '%s%s\n' "$origin" "$PUBLIC_BASE_PATH"
}

LOCAL_SMOKE_BASE_URL="$(resolve_local_smoke_base_url)"

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
  scripts/server/smoke-test.sh "$LOCAL_SMOKE_BASE_URL"
fi

echo "Rollback to $TARGET_TAG completed."
