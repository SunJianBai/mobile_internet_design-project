#!/usr/bin/env bash
set -euo pipefail

TARGET_RELEASE="${1:-}"
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

if [ -z "$TARGET_RELEASE" ]; then
  if [ ! -f .env.fast.release.previous ]; then
    echo "No previous fast release recorded. Pass a release directory or tag explicitly." >&2
    exit 66
  fi
  TARGET_RELEASE="$(sed -n 's/^CAMPUSHUB_FAST_RELEASE=//p' .env.fast.release.previous | tail -n 1)"
fi

case "$TARGET_RELEASE" in
  /*) RELEASE_DIR="$TARGET_RELEASE" ;;
  *) RELEASE_DIR="${FAST_RELEASES_DIR:-$DEPLOY_DIR/fast-releases}/$TARGET_RELEASE" ;;
esac

if [ ! -d "$RELEASE_DIR" ]; then
  echo "Fast rollback release not found: $RELEASE_DIR" >&2
  exit 66
fi

test -f "$RELEASE_DIR/web/dist/index.html"
test -f "$RELEASE_DIR/agent/app/main.py"
test -f "$RELEASE_DIR/backend/app.jar"

CURRENT_TARGET=""
if [ -L current ] || [ -e current ]; then
  CURRENT_TARGET="$(readlink -f current || true)"
fi
if [ -n "$CURRENT_TARGET" ] && [ "$CURRENT_TARGET" != "$RELEASE_DIR" ]; then
  printf 'CAMPUSHUB_FAST_RELEASE=%s\n' "$CURRENT_TARGET" > .env.fast.release.previous
fi

ln -sfn "$RELEASE_DIR" current.next
mv -Tf current.next current
printf 'CAMPUSHUB_FAST_RELEASE=%s\n' "$RELEASE_DIR" > .env.fast.release

echo "Rolling CampusHub fast release back to $RELEASE_DIR"
sudo docker compose --env-file .env.prod --env-file .env.fast -f docker-compose.fast.yml up -d --no-build --force-recreate agent backend frontend
sudo docker compose --env-file .env.prod --env-file .env.fast -f docker-compose.fast.yml ps

if [ -x scripts/server/smoke-test.sh ]; then
  scripts/server/smoke-test.sh "$LOCAL_SMOKE_BASE_URL"
fi

echo "Fast rollback completed."
