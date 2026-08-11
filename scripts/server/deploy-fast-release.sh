#!/usr/bin/env bash
set -euo pipefail

RELEASE_TAG="${1:-}"
BUNDLE_PATH="${2:-}"
PUBLIC_BASE_URL="${3:-${PUBLIC_BASE_URL:-https://sun227454.online/CampusHub}}"
DEPLOY_DIR="${DEPLOY_DIR:-/home/ubuntu/CampusHub}"
FAST_RELEASES_DIR="${FAST_RELEASES_DIR:-$DEPLOY_DIR/fast-releases}"
PUBLIC_BASE_PATH="$(printf '%s' "$PUBLIC_BASE_URL" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]*##; s#/*$##')"
LOCAL_SMOKE_BASE_URL="${LOCAL_SMOKE_BASE_URL:-}"

if [ -z "$RELEASE_TAG" ] || [ -z "$BUNDLE_PATH" ]; then
  echo "Usage: scripts/server/deploy-fast-release.sh <release-tag> <artifact-bundle> [public-base-url]" >&2
  exit 64
fi

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

if [ ! -f "$BUNDLE_PATH" ]; then
  echo "Fast artifact bundle not found: $BUNDLE_PATH" >&2
  exit 66
fi

if [ ! -f docker-compose.fast.yml ]; then
  echo "docker-compose.fast.yml is missing in $DEPLOY_DIR" >&2
  exit 66
fi

mkdir -p "$FAST_RELEASES_DIR" backups
RELEASE_DIR="$FAST_RELEASES_DIR/$RELEASE_TAG"
PREVIOUS_TARGET=""
if [ -L current ] || [ -e current ]; then
  PREVIOUS_TARGET="$(readlink -f current || true)"
fi

rm -rf "$RELEASE_DIR.tmp"
mkdir -p "$RELEASE_DIR.tmp"
tar -xzf "$BUNDLE_PATH" -C "$RELEASE_DIR.tmp"

if [ ! -f "$RELEASE_DIR.tmp/manifest.json" ]; then
  echo "manifest.json is missing from fast artifact bundle" >&2
  exit 65
fi

if [ -n "$PREVIOUS_TARGET" ] && [ -d "$PREVIOUS_TARGET" ]; then
  for module in web agent backend; do
    if [ ! -e "$RELEASE_DIR.tmp/$module" ] && [ -e "$PREVIOUS_TARGET/$module" ]; then
      cp -a "$PREVIOUS_TARGET/$module" "$RELEASE_DIR.tmp/$module"
    fi
  done
fi
sudo chown -R "$(id -u):$(id -g)" "$RELEASE_DIR.tmp" 2>/dev/null || true

test -f "$RELEASE_DIR.tmp/web/dist/index.html"
test -f "$RELEASE_DIR.tmp/agent/app/main.py"
test -f "$RELEASE_DIR.tmp/backend/app.jar"

rm -rf "$RELEASE_DIR"
mv "$RELEASE_DIR.tmp" "$RELEASE_DIR"

ensure_fast_env() {
  if [ -f .env.fast ]; then
    return
  fi
  agent_image="$(sudo docker inspect -f '{{.Config.Image}}' campushub_agent 2>/dev/null || true)"
  backend_image="$(sudo docker inspect -f '{{.Config.Image}}' campushub_backend 2>/dev/null || true)"
  web_image="$(sudo docker inspect -f '{{.Config.Image}}' campushub_frontend 2>/dev/null || true)"
  if [ -z "$agent_image" ] || [ -z "$backend_image" ] || [ -z "$web_image" ]; then
    echo "Cannot infer current runtime images for .env.fast" >&2
    exit 66
  fi
  {
    printf 'CAMPUSHUB_AGENT_IMAGE_TAG=%s\n' "${agent_image##*:}"
    printf 'CAMPUSHUB_BACKEND_IMAGE_TAG=%s\n' "${backend_image##*:}"
    printf 'CAMPUSHUB_WEB_IMAGE_TAG=%s\n' "${web_image##*:}"
  } > .env.fast
}

manifest_modules() {
  python3 - "$RELEASE_DIR/manifest.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
modules = data.get("modules") or []
print(" ".join(str(item) for item in modules if item in {"web", "agent", "backend"}))
PY
}

services_for_modules() {
  local modules="$1"
  local services=()
  case " $modules " in *" agent "*) services+=("agent");; esac
  case " $modules " in *" backend "*) services+=("backend");; esac
  case " $modules " in *" web "*) services+=("frontend");; esac
  if [ "${#services[@]}" -eq 0 ]; then
    services=("agent" "backend" "frontend")
  fi
  printf '%s\n' "${services[@]}"
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

ensure_fast_env
MODULES="$(manifest_modules)"
mapfile -t SERVICES < <(services_for_modules "$MODULES")
if [ -z "$PREVIOUS_TARGET" ] || [ ! -d "$PREVIOUS_TARGET" ]; then
  SERVICES=("agent" "backend" "frontend")
fi

if [ -n "$PREVIOUS_TARGET" ] && [ "$PREVIOUS_TARGET" != "$RELEASE_DIR" ]; then
  printf 'CAMPUSHUB_FAST_RELEASE=%s\n' "$PREVIOUS_TARGET" > .env.fast.release.previous
  printf 'CAMPUSHUB_FAST_RELEASE=%s\n' "$PREVIOUS_TARGET" > "backups/fast-previous-before-$RELEASE_TAG.env"
fi

ln -sfn "$RELEASE_DIR" current.next
mv -Tf current.next current
printf 'CAMPUSHUB_FAST_RELEASE=%s\n' "$RELEASE_DIR" > .env.fast.release

rollback_current() {
  if [ -n "$PREVIOUS_TARGET" ] && [ -d "$PREVIOUS_TARGET" ]; then
    echo "Fast deploy failed; rolling current symlink back to $PREVIOUS_TARGET" >&2
    ln -sfn "$PREVIOUS_TARGET" current.next
    mv -Tf current.next current
    sudo docker compose --env-file .env.prod --env-file .env.fast -f docker-compose.fast.yml up -d --no-build --force-recreate "${SERVICES[@]}" || true
  fi
}

trap 'status=$?; if [ "$status" -ne 0 ]; then rollback_current; fi; exit "$status"' EXIT

echo "Starting fast CampusHub release $RELEASE_TAG for modules: ${MODULES:-all}"
sudo docker compose --env-file .env.prod --env-file .env.fast -f docker-compose.fast.yml up -d --no-build --force-recreate "${SERVICES[@]}"
sudo docker compose --env-file .env.prod --env-file .env.fast -f docker-compose.fast.yml ps

if [ -x scripts/server/smoke-test.sh ]; then
  scripts/server/smoke-test.sh "$LOCAL_SMOKE_BASE_URL"
fi
prune_fast_releases || true

trap - EXIT
echo "Fast release $RELEASE_TAG deployed successfully."
