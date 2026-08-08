#!/usr/bin/env bash
set -euo pipefail

# JoJo Hub fresh-OS bootstrap.
# Intended for a new Ubuntu installation where the runtime user is `admini`.
# No passwords/tokens/Wi-Fi secrets are embedded in this script.

RUNTIME_USER="${JOJOS_USER:-admini}"
RUNTIME_HOME="/home/${RUNTIME_USER}"
REPO_URL="${JOJOS_REPO_URL:-https://github.com/nomaddase/jojos-hub.git}"
CHECKOUT="${RUNTIME_HOME}/jojos-monorepo"
CORE="${RUNTIME_HOME}/jojos-core"
UI="${RUNTIME_HOME}/jojos-ui"

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/bootstrap-fresh-ubuntu.sh"
  exit 1
fi

if ! id "${RUNTIME_USER}" >/dev/null 2>&1; then
  echo "Required runtime user '${RUNTIME_USER}' does not exist."
  echo "Create it during OS install or with: adduser ${RUNTIME_USER}"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  sudo ca-certificates curl git jq rsync sqlite3 \
  python3 python3-venv python3-pip \
  nodejs npm \
  openssh-server network-manager

systemctl enable --now ssh

install -d -o "${RUNTIME_USER}" -g "${RUNTIME_USER}" "${RUNTIME_HOME}/jojos-backups/hub"
install -d -o "${RUNTIME_USER}" -g "${RUNTIME_USER}" "${RUNTIME_HOME}/jojos-releases/kso"
install -d -o "${RUNTIME_USER}" -g "${RUNTIME_USER}" "${RUNTIME_HOME}/jojos-releases/kitchen"

if [ -d "${CHECKOUT}/.git" ]; then
  sudo -u "${RUNTIME_USER}" git -C "${CHECKOUT}" fetch origin
  sudo -u "${RUNTIME_USER}" git -C "${CHECKOUT}" checkout main
  sudo -u "${RUNTIME_USER}" git -C "${CHECKOUT}" reset --hard origin/main
else
  rm -rf "${CHECKOUT}"
  sudo -u "${RUNTIME_USER}" git clone "${REPO_URL}" "${CHECKOUT}"
fi

install -d -o "${RUNTIME_USER}" -g "${RUNTIME_USER}" "${CORE}" "${UI}"

rsync -a --delete \
  --exclude 'venv/' \
  --exclude '.venv/' \
  --exclude 'jojos_core.db' \
  --exclude 'config/' \
  --exclude 'data/' \
  --exclude 'static/' \
  --exclude '__pycache__/' \
  "${CHECKOUT}/jojos-core/" "${CORE}/"

rsync -a --delete \
  --exclude 'node_modules/' \
  --exclude 'dist/' \
  "${CHECKOUT}/jojos-ui/" "${UI}/"

chown -R "${RUNTIME_USER}:${RUNTIME_USER}" "${CORE}" "${UI}" "${CHECKOUT}"

if [ ! -x "${CORE}/venv/bin/python" ]; then
  sudo -u "${RUNTIME_USER}" python3 -m venv "${CORE}/venv"
fi

if [ -f "${CORE}/requirements.txt" ]; then
  sudo -u "${RUNTIME_USER}" "${CORE}/venv/bin/pip" install --upgrade pip
  sudo -u "${RUNTIME_USER}" "${CORE}/venv/bin/pip" install -r "${CORE}/requirements.txt"
fi

sudo -u "${RUNTIME_USER}" "${CORE}/venv/bin/python" -m compileall "${CORE}/app"

if [ -f "${UI}/package.json" ]; then
  cd "${UI}"
  if [ -f package-lock.json ]; then
    sudo -u "${RUNTIME_USER}" npm ci
  else
    sudo -u "${RUNTIME_USER}" npm install
  fi
  sudo -u "${RUNTIME_USER}" npm run build
  rm -rf "${CORE}/static"
  install -d -o "${RUNTIME_USER}" -g "${RUNTIME_USER}" "${CORE}/static"
  cp -a "${UI}/dist/." "${CORE}/static/"
  chown -R "${RUNTIME_USER}:${RUNTIME_USER}" "${CORE}/static"
fi

install -m 0644 "${CHECKOUT}/deploy/systemd/jojos-core.service" /etc/systemd/system/jojos-core.service
systemctl daemon-reload
systemctl enable --now jojos-core.service

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/api/health; then
    echo
    echo "JoJo Core is healthy."
    echo "Checkout: ${CHECKOUT}"
    echo "Runtime:  ${CORE}"
    echo "Next: configure LAN/Wi-Fi and GitHub self-hosted runners."
    exit 0
  fi
  sleep 1
done

echo "JoJo Core health check failed."
systemctl status jojos-core.service --no-pager || true
journalctl -u jojos-core.service -n 100 --no-pager || true
exit 1
