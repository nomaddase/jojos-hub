#!/usr/bin/env bash
set -euo pipefail

# Configure every JoJo store hub with the same store Wi-Fi.
# The SSID and address are public configuration. The shared password is supplied
# at runtime either from Central Base or from the private jojos-base repository.
#
# Defaults:
#   SSID:    JoJos-Hub
#   Hub IP:  192.168.50.1/24
#
# Required:
#   JOJOS_WIFI_PASSWORD=...
#
# Optional overrides:
#   JOJOS_WIFI_SSID=...
#   JOJOS_WIFI_IFACE=wlan0
#   JOJOS_WIFI_ADDRESS=192.168.50.1/24

SSID="${JOJOS_WIFI_SSID:-JoJos-Hub}"
PSK="${JOJOS_WIFI_PASSWORD:-}"
ADDR="${JOJOS_WIFI_ADDRESS:-192.168.50.1/24}"
CON_NAME="${JOJOS_WIFI_CONNECTION:-jojos-hotspot}"
IFACE="${JOJOS_WIFI_IFACE:-}"

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo."
  exit 1
fi

if [ -z "${PSK}" ]; then
  echo "JOJOS_WIFI_PASSWORD is required."
  exit 1
fi

PSK_BYTES="$(printf '%s' "${PSK}" | wc -c)"
if [ "${PSK_BYTES}" -lt 8 ] || [ "${PSK_BYTES}" -gt 63 ]; then
  echo "Wi-Fi password must contain 8..63 bytes."
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

if nmcli -t -f NAME connection show | grep -Fxq "${CON_NAME}"; then
  nmcli connection modify "${CON_NAME}" \
    connection.interface-name "${IFACE}" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    802-11-wireless.ssid "${SSID}" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    ipv4.method shared \
    ipv4.addresses "${ADDR}" \
    ipv6.method disabled \
    802-11-wireless-security.key-mgmt wpa-psk \
    802-11-wireless-security.proto rsn \
    802-11-wireless-security.pairwise ccmp \
    802-11-wireless-security.group ccmp \
    802-11-wireless-security.pmf 1 \
    802-11-wireless-security.psk "${PSK}"
else
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
    802-11-wireless-security.key-mgmt wpa-psk \
    802-11-wireless-security.proto rsn \
    802-11-wireless-security.pairwise ccmp \
    802-11-wireless-security.group ccmp \
    802-11-wireless-security.pmf 1 \
    802-11-wireless-security.psk "${PSK}"
fi

# Re-activate so changed SSID/password/security settings take effect immediately.
nmcli connection down "${CON_NAME}" >/dev/null 2>&1 || true
nmcli connection up "${CON_NAME}"

echo "Hotspot '${SSID}' is active on ${IFACE}."
echo "Hub address: ${ADDR}"
echo "Security: WPA2-PSK (RSN/CCMP), PMF disabled for broad Android compatibility."
echo "KSO/Kitchen default Hub URL: http://${ADDR%/*}:8080"
