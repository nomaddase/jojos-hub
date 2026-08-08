#!/usr/bin/env bash
set -euo pipefail

BASE="${JOJOS_BASE_URL:-http://127.0.0.1:8080}"

check_json() {
  local path="$1"
  echo "==> GET ${path}"
  curl -fsS "${BASE}${path}" >/tmp/jojos-check.json
  python3 -m json.tool /tmp/jojos-check.json >/dev/null
}

check_json /api/health
check_json /api/settings
check_json /api/catalog
check_json /api/kitchen/orders
check_json /api/display/orders

echo "==> SSE kitchen"
KITCHEN_SSE="$(timeout 4s curl -fsSN "${BASE}/api/events/kitchen" || true)"
printf '%s\n' "${KITCHEN_SSE}" | grep -Eq 'event: (kitchen_update|heartbeat)'

echo "==> SSE display"
DISPLAY_SSE="$(timeout 4s curl -fsSN "${BASE}/api/events/display" || true)"
printf '%s\n' "${DISPLAY_SSE}" | grep -Eq 'event: (display_update|heartbeat)'

echo "All basic JoJo Hub checks passed."
