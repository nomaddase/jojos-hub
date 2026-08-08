#!/usr/bin/env bash
set -euo pipefail

# Apply the network settings currently delivered by Central Base in the Hub bootstrap.
# This script never prints the Wi-Fi password.

BOOTSTRAP="${JOJOS_BOOTSTRAP_PATH:-/home/admini/jojos-core/config/central_bootstrap.json}"
SETUP_SCRIPT="${JOJOS_HOTSPOT_SETUP:-/home/admini/jojos-monorepo/deploy/setup-hotspot.sh}"

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/apply-central-network.sh"
  exit 1
fi

if [ ! -f "${BOOTSTRAP}" ]; then
  echo "Central bootstrap is not available yet: ${BOOTSTRAP}"
  exit 1
fi

if [ ! -f "${SETUP_SCRIPT}" ]; then
  echo "Hotspot setup script not found: ${SETUP_SCRIPT}"
  exit 1
fi

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT
chmod 600 "${TMP}"

python3 - "${BOOTSTRAP}" "${TMP}" <<'PY'
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

# Shell-quoted temporary environment file, mode 0600. Password is never echoed.
with open(target, "w", encoding="utf-8") as out:
    out.write(f"JOJOS_WIFI_SSID={shlex.quote(ssid)}\n")
    out.write(f"JOJOS_WIFI_PASSWORD={shlex.quote(password)}\n")
    out.write(f"JOJOS_WIFI_ADDRESS={shlex.quote(hub_ip + '/24')}\n")
    out.write("JOJOS_WIFI_CONNECTION=jojos-hotspot\n")
PY

# shellcheck disable=SC1090
set -a
source "${TMP}"
set +a

bash "${SETUP_SCRIPT}"

echo "Central Base Wi-Fi settings were applied to the physical Hub hotspot."
