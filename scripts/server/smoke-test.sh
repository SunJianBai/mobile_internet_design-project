#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${PUBLIC_BASE_URL:-https://sun227454.online/CampusHub}}"
BASE_URL="${BASE_URL%/}"
API_URL="$BASE_URL/api/v1/orders?page=1&size=1"
RETRIES="${SMOKE_RETRIES:-10}"
DELAY_SECONDS="${SMOKE_DELAY_SECONDS:-5}"

retry() {
  local name="$1"
  shift
  local attempt
  for attempt in $(seq 1 "$RETRIES"); do
    echo "Checking $name (attempt $attempt/$RETRIES)" >&2
    if "$@"; then
      return 0
    fi
    if [ "$attempt" -eq "$RETRIES" ]; then
      return 1
    fi
    echo "Check failed, retrying in $DELAY_SECONDS seconds..." >&2
    sleep "$DELAY_SECONDS"
  done
}

check_home() {
  curl -fsSI --max-time 15 "$BASE_URL/" >/dev/null
}

retry "$BASE_URL/" check_home

API_RESPONSE="$(retry "$API_URL" curl -fsS --max-time 15 "$API_URL")"
case "$API_RESPONSE" in
  *'"code":200'*)
    echo "Smoke test passed: $BASE_URL"
    ;;
  *)
    echo "Unexpected API response: $API_RESPONSE" >&2
    exit 1
    ;;
esac
