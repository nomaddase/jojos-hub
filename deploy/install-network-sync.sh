#!/usr/bin/env bash
set -euo pipefail

# One-time privileged installation of Central Base -> physical hotspot sync.
# Run from the jojos-hub checkout:
#   sudo bash deploy/install-network-sync.sh

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/install-network-sync.sh"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

install -m 0755 "${ROOT_DIR}/deploy/setup-hotspot.sh" /usr/local/sbin/jojos-setup-hotspot
install -m 0755 "${ROOT_DIR}/deploy/apply-central-network.sh" /usr/local/sbin/jojos-apply-central-network
install -m 0644 "${ROOT_DIR}/deploy/systemd/jojos-network-sync.service" /etc/systemd/system/jojos-network-sync.service
install -m 0644 "${ROOT_DIR}/deploy/systemd/jojos-network-sync.path" /etc/systemd/system/jojos-network-sync.path
install -m 0644 "${ROOT_DIR}/deploy/systemd/jojos-network-sync.timer" /etc/systemd/system/jojos-network-sync.timer

systemctl daemon-reload
systemctl enable --now jojos-network-sync.path jojos-network-sync.timer
systemctl start jojos-network-sync.service

systemctl --no-pager --full status jojos-network-sync.service || true
systemctl --no-pager --full status jojos-network-sync.path || true
systemctl --no-pager --full status jojos-network-sync.timer || true

echo "JoJo Central Wi-Fi sync is installed."
echo "Future Wi-Fi changes saved in Base will be applied automatically after Hub sync."
