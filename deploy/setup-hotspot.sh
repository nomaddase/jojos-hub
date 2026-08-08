#!/usr/bin/env bash
set -euo pipefail

# Configure every JoJo store hub with the same recovery/store Wi-Fi.
# These credentials are intentionally static so KSO/Kitchen devices can move
# between stores, reconnect automatically, and then re-bind to the new Hub ID.
# The project owner explicitly chose to keep these store-LAN credentials in Git.
#
# Defaults:
#   SSID:    JoJos-Hub
#   Password: JoJosHub2026!
#   Hub IP:  192.168.50.1/24
#
# Optional overrides are still supported for exceptional installations:
#   JOJOS_WIFI_SSID=...
#   JOJOS_WIFI_PASSWORD=...
#   JOJOS_WIFI_IFACE=wlan0
#   JOJOS_WIFI_ADDRESS=192.168.50.1/24

SSID="${JOJOS_WIFI_SSID:-JoJos-Hub}"
PSK="${JOJOS_WIFI_PASSWORD:-JoJosHub2026!}"
ADDR="${JOJOS_WIFI_ADDRESS:-192.168.50.1/24}"
CON_NAME="${JOJOS_WIFI_CONNECTION:-jojos-hotspot}"
IFACE="${JOJOS_WIFI_IFACE:-}"

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo."
  exit 1
fi

if [ ${#PSK} -lt 8 ]; then
  echo "Wi-Fi password must contain at least 8 characters."
  exit 1
fi

if [ -z "${IFACE}" ]; then
  IFACE="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi" {print $1; exit}')"
fi

if [ -z "${IFACE}" ]; then
  echo "No Wi-Fi interface found. Set JOJOS_WIFI_IFACE explicitly."
  exit 1
fi

nmcli radio wifi on
nmcli connection delete "${CON_NAME}" >/dev/null 2>&1 || true

nmcli connection add \
  type wifi \
  ifname "${IFACE}" \
  con-name "${CON_NAME}" \
  autoconnect yes \
  ssid "${SSID}"

nmcli connection modify "${CON_NAME}" \
  connection.autoconnect yes \
  connection.autoconnect-priority 100 \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  ipv4.method shared \
  ipv4.addresses "${ADDR}" \
  ipv6.method disabled \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "${PSK}"

nmcli connection up "${CON_NAME}"

echo "Hotspot '${SSID}' is active on ${IFACE}."
echo "Hub address: ${ADDR}"
echo "KSO/Kitchen default Hub URL: http://${ADDR%/*}:8080"
