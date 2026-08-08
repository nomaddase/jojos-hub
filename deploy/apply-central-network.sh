#!/usr/bin/env bash
set -euo pipefail

# Apply the network settings currently delivered by Central Base.
# Network policy is cached separately from the frequently refreshed operational
# bootstrap so catalog/inventory sync can never bounce the store Wi-Fi.
# The hotspot is restarted only when SSID/password/IP actually changed, or when
# the hotspot is not active. This script never prints the Wi-Fi password.

NETWORK_POLICY="${JOJOS_NETWORK_POLICY_PATH:-/home/admini/jojos-core/config/central_network.json}"
SETUP_SCRIPT="${JOJOS_HOTSPOT_SETUP:-/usr/local/sbin/jojos-setup-hotspot}"
STATE_DIR="${JOJOS_NETWORK_STATE_DIR:-/var/lib/jojos}"
STATE_FILE="${STATE_DIR}/network-settings.sha256"

if [ "${EUID}" -ne 0 ]; then
  echo "Run as root."
  exit 1
fi

if [ ! -f "${NETWORK_POLICY}" ]; then
  echo "Central network policy is not available yet: ${NETWORK_POLICY}"
  exit 1
fi

if [ ! -x "${SETUP_SCRIPT}" ]; then
  echo "Hotspot setup helper not found: ${SETUP_SCRIPT}"
  exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT
chmod 600 "${TMP}"

python3 - "${NETWORK_POLICY}" "${TMP}" <<'PY'
import hashlib
import ipaddress
import json
import shlex
import sys

source, target = sys.argv[1], sys.argv[2]
with open(source, "r", encoding="utf-8") as f:
    payload = json.load(f)
network = ((payload.get("settings") or {}).get("network") or {})
ssid = str(network.get("ssid") or "").strip()
password = str(network.get("password") or "")
hub_ip = str(network.get("hub_ip") or "192.168.50.1").strip()

if not ssid:
    raise SystemExit("Central Base returned an empty Wi-Fi SSID")
if not 8 <= len(password.encode("utf-8")) <= 63:
    raise SystemExit("Central Base Wi-Fi password must be 8..63 bytes")
try:
    ipaddress.ip_address(hub_ip)
except ValueError as exc:
    raise SystemExit(f"Invalid Hub IP from Central Base: {hub_ip}") from exc

fingerprint = hashlib.sha256(
    json.dumps(
        {"ssid": ssid, "password": password, "hub_ip": hub_ip},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()

with open(target, "w", encoding="utf-8") as out:
    out.write(f"JOJOS_WIFI_SSID={shlex.quote(ssid)}\n")
    out.write(f"JOJOS_WIFI_PASSWORD={shlex.quote(password)}\n")
    out.write(f"JOJOS_WIFI_ADDRESS={shlex.quote(hub_ip + '/24')}\n")
    out.write("JOJOS_WIFI_CONNECTION=jojos-hotspot\n")
    out.write(f"JOJOS_NETWORK_FINGERPRINT={shlex.quote(fingerprint)}\n")
PY

# shellcheck disable=SC1090
set -a
source "${TMP}"
set +a

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

ACTIVE=0
if nmcli -t -f NAME connection show --active | grep -Fxq "${JOJOS_WIFI_CONNECTION}"; then
  ACTIVE=1
fi

APPLIED=""
if [ -f "${STATE_FILE}" ]; then
  APPLIED="$(cat "${STATE_FILE}" 2>/dev/null || true)"
fi

if [ "${ACTIVE}" -eq 1 ] && [ -n "${APPLIED}" ] && [ "${APPLIED}" = "${JOJOS_NETWORK_FINGERPRINT}" ]; then
  echo "Central Wi-Fi settings unchanged; hotspot stays up without reconnecting clients."
  exit 0
fi

"${SETUP_SCRIPT}"

STATE_TMP="${STATE_FILE}.tmp"
printf '%s\n' "${JOJOS_NETWORK_FINGERPRINT}" > "${STATE_TMP}"
chmod 600 "${STATE_TMP}"
mv -f "${STATE_TMP}" "${STATE_FILE}"

echo "Central Base Wi-Fi settings were applied to the physical Hub hotspot."
