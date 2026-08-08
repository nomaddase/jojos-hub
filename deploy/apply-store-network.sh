#!/usr/bin/env bash
set -euo pipefail

# Fetch the shared store-network configuration from the private jojos-base repo
# using the current user's GitHub CLI authorization, then apply it with sudo.
# No Wi-Fi password is printed or stored in this public repository.

PRIVATE_REPO="${JOJOS_NETWORK_REPO:-nomaddase/jojos-base}"
PRIVATE_PATH="${JOJOS_NETWORK_PATH:-config/store-network.env}"
CHECKOUT="${JOJOS_HUB_CHECKOUT:-/home/admini/jojos-monorepo}"

if [ "${EUID}" -eq 0 ]; then
  echo "Run as the normal Hub user, not root. This script invokes sudo itself."
  exit 1
fi

for cmd in gh base64 sudo; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing command: ${cmd}"; exit 1; }
done

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated for this user."
  exit 1
fi

if [ ! -f "${CHECKOUT}/deploy/setup-hotspot.sh" ]; then
  echo "Missing ${CHECKOUT}/deploy/setup-hotspot.sh"
  exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT
chmod 600 "${TMP}"

gh api "repos/${PRIVATE_REPO}/contents/${PRIVATE_PATH}" --jq .content \
  | tr -d '\n' \
  | base64 -d >"${TMP}"

# shellcheck disable=SC1090
set -a
source "${TMP}"
set +a

if [ -z "${JOJOS_WIFI_PASSWORD:-}" ]; then
  echo "Private store-network config does not contain JOJOS_WIFI_PASSWORD."
  exit 1
fi

sudo \
  JOJOS_WIFI_SSID="${JOJOS_WIFI_SSID:-JoJos-Hub}" \
  JOJOS_WIFI_PASSWORD="${JOJOS_WIFI_PASSWORD}" \
  JOJOS_WIFI_ADDRESS="${JOJOS_WIFI_ADDRESS:-192.168.50.1/24}" \
  JOJOS_WIFI_CONNECTION="${JOJOS_WIFI_CONNECTION:-jojos-hotspot}" \
  JOJOS_WIFI_IFACE="${JOJOS_WIFI_IFACE:-}" \
  bash "${CHECKOUT}/deploy/setup-hotspot.sh"

echo "Store Wi-Fi applied from private configuration."
