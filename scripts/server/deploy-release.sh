#!/usr/bin/env bash
set -euo pipefail

RELEASE_TAG="${1:-}"
BUNDLE_PATH="${2:-}"
PUBLIC_BASE_URL="${3:-${PUBLIC_BASE_URL:-https://sun227454.online/CampusHub}}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/ubuntu/CampusHub}"
FAST_RELEASES_DIR="${FAST_RELEASES_DIR:-$DEPLOY_DIR/fast-releases}"
PUBLIC_BASE_PATH="$(printf '%s' "$PUBLIC_BASE_URL" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]*##; s#/*$##')"
LOCAL_SMOKE_BASE_URL="${LOCAL_SMOKE_BASE_URL:-}"

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

seed_fast_release_baseline() {
  local baseline_dir tmp_dir
  baseline_dir="$FAST_RELEASES_DIR/full-$RELEASE_TAG"
  tmp_dir="$baseline_dir.tmp"

  mkdir -p "$FAST_RELEASES_DIR"
  sudo rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir/web" "$tmp_dir/backend" "$tmp_dir/agent"

  sudo docker cp campushub_frontend:/usr/share/nginx/html/CampusHub "$tmp_dir/web/dist"
  sudo docker cp campushub_backend:/app/app.jar "$tmp_dir/backend/app.jar"
  sudo docker cp campushub_agent:/app/app "$tmp_dir/agent/app"
  sudo chown -R "$(id -u):$(id -g)" "$tmp_dir"

  python3 - "$tmp_dir/manifest.json" "$RELEASE_TAG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

manifest_path = Path(sys.argv[1])
release_tag = sys.argv[2]
manifest_path.write_text(
    json.dumps(
        {
            "release_tag": release_tag,
            "source": "full-image-deploy",
            "modules": ["web", "agent", "backend"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
PY

  test -f "$tmp_dir/web/dist/index.html"
  test -f "$tmp_dir/backend/app.jar"
  test -f "$tmp_dir/agent/app/main.py"

  sudo rm -rf "$baseline_dir"
  mv "$tmp_dir" "$baseline_dir"
  ln -sfn "$baseline_dir" current.next
  mv -Tf current.next current

  {
    printf 'CAMPUSHUB_AGENT_IMAGE_TAG=%s\n' "$RELEASE_TAG"
    printf 'CAMPUSHUB_BACKEND_IMAGE_TAG=%s\n' "$RELEASE_TAG"
    printf 'CAMPUSHUB_WEB_IMAGE_TAG=%s\n' "$RELEASE_TAG"
  } > .env.fast
  printf 'CAMPUSHUB_FAST_RELEASE=%s\n' "$baseline_dir" > .env.fast.release
  echo "Seeded fast deploy baseline from full release $RELEASE_TAG."
}

prune_fast_releases() {
  local keep current_target previous_target count dir
  keep="${FAST_RELEASE_KEEP:-8}"
  case "$keep" in
    ''|*[!0-9]*) return ;;
  esac
  if [ "$keep" -le 0 ]; then
    return
  fi

  current_target="$(readlink -f current 2>/dev/null || true)"
  previous_target="$(sed -n 's/^CAMPUSHUB_FAST_RELEASE=//p' .env.fast.release.previous 2>/dev/null | tail -n 1 || true)"
  count=0

  while IFS= read -r dir; do
    if [ -z "$dir" ] || [ "$dir" = "$current_target" ] || [ "$dir" = "$previous_target" ]; then
      continue
    fi
    count=$((count + 1))
    if [ "$count" -gt "$keep" ]; then
      echo "Pruning old fast release $dir"
      sudo rm -rf "$dir"
    fi
  done < <(find "$FAST_RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -rn | awk '{print $2}')
}

seed_fast_release_baseline

if [ -x scripts/server/smoke-test.sh ]; then
  scripts/server/smoke-test.sh "$LOCAL_SMOKE_BASE_URL"
fi
prune_fast_releases || true

echo "Release $RELEASE_TAG deployed successfully."
