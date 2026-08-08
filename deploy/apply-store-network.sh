#!/usr/bin/env bash
set -euo pipefail

# Fetch the shared store-network configuration from the private jojos-base repo,
# apply the Wi-Fi hotspot, and expose JoJo Core on local HTTP port 80.
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

for file in \
  "${CHECKOUT}/deploy/setup-hotspot.sh" \
  "${CHECKOUT}/deploy/systemd/jojos-http-proxy.socket" \
  "${CHECKOUT}/deploy/systemd/jojos-http-proxy.service"; do
  if [ ! -f "${file}" ]; then
    echo "Missing ${file}"
    exit 1
  fi
done

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

if [ ! -x /usr/lib/systemd/systemd-socket-proxyd ]; then
  echo "systemd-socket-proxyd is missing; cannot expose local port 80."
  exit 1
fi

sudo install -m 0644 \
  "${CHECKOUT}/deploy/systemd/jojos-http-proxy.socket" \
  /etc/systemd/system/jojos-http-proxy.socket
sudo install -m 0644 \
  "${CHECKOUT}/deploy/systemd/jojos-http-proxy.service" \
  /etc/systemd/system/jojos-http-proxy.service
sudo systemctl daemon-reload
sudo systemctl enable --now jojos-http-proxy.socket

HUB_IP="${JOJOS_WIFI_ADDRESS:-192.168.50.1/24}"
HUB_IP="${HUB_IP%/*}"

echo "Store Wi-Fi applied from private configuration."
echo "Local installer URLs:"
echo "  http://${HUB_IP}/download/kso"
echo "  http://${HUB_IP}/download/kitchen"
