#!/usr/bin/env bash
set -euo pipefail

# Configure the hub as a Wi-Fi hotspot using NetworkManager.
# Secrets are passed at runtime and are never stored in Git.
#
# Example:
#   sudo JOJOS_WIFI_SSID='JoJo-Hub' JOJOS_WIFI_PASSWORD='strong-password' bash deploy/setup-hotspot.sh
#
# Optional:
#   JOJOS_WIFI_IFACE=wlan0
#   JOJOS_WIFI_ADDRESS=192.168.50.1/24

SSID="${JOJOS_WIFI_SSID:-}"
PSK="${JOJOS_WIFI_PASSWORD:-}"
ADDR="${JOJOS_WIFI_ADDRESS:-192.168.50.1/24}"
CON_NAME="${JOJOS_WIFI_CONNECTION:-jojos-hotspot}"
IFACE="${JOJOS_WIFI_IFACE:-}"

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo."
  exit 1
fi

if [ -z "${SSID}" ] || [ -z "${PSK}" ]; then
  echo "JOJOS_WIFI_SSID and JOJOS_WIFI_PASSWORD are required."
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

nmcli connection delete "${CON_NAME}" >/dev/null 2>&1 || true

nmcli connection add \
  type wifi \
  ifname "${IFACE}" \
  con-name "${CON_NAME}" \
  autoconnect yes \
  ssid "${SSID}"

nmcli connection modify "${CON_NAME}" \
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
echo "Keep the password outside Git (password manager / deployment secret)."
