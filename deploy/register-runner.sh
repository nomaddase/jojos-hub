#!/usr/bin/env bash
set -euo pipefail

# Register one GitHub Actions self-hosted runner on the JoJo hub.
# Usage:
#   sudo -u admini GH_RUNNER_TOKEN=... bash deploy/register-runner.sh nomaddase/jojos-hub jojos-hub
#   sudo -u admini GH_RUNNER_TOKEN=... bash deploy/register-runner.sh nomaddase/jojos-kso jojos-kso
#   sudo -u admini GH_RUNNER_TOKEN=... bash deploy/register-runner.sh nomaddase/jojos-kitchen jojos-kitchen
#
# Registration tokens are short-lived and must never be committed.

REPO="${1:-}"
LABEL="${2:-}"
TOKEN="${GH_RUNNER_TOKEN:-}"

if [ -z "${REPO}" ] || [ -z "${LABEL}" ] || [ -z "${TOKEN}" ]; then
  echo "Usage: GH_RUNNER_TOKEN=... $0 owner/repo label"
  exit 1
fi

BASE="${HOME}/actions-runners"
DEST="${BASE}/${LABEL}"
mkdir -p "${BASE}" "${DEST}"

API_JSON="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest)"
TAG="$(printf '%s' "${API_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
VER="${TAG#v}"
ARCHIVE="/tmp/actions-runner-${VER}.tar.gz"

if [ ! -x "${DEST}/config.sh" ]; then
  curl -fL "https://github.com/actions/runner/releases/download/${TAG}/actions-runner-linux-x64-${VER}.tar.gz" -o "${ARCHIVE}"
  tar xzf "${ARCHIVE}" -C "${DEST}"
fi

cd "${DEST}"

if [ -f .runner ]; then
  echo "Runner already configured in ${DEST}"
  exit 0
fi

./config.sh \
  --url "https://github.com/${REPO}" \
  --token "${TOKEN}" \
  --name "$(hostname)-${LABEL}" \
  --labels "${LABEL}" \
  --work "_work" \
  --unattended

echo
cat <<EOF
Runner configured.
Install/start its service from this directory with:
  sudo ./svc.sh install $(whoami)
  sudo ./svc.sh start
  sudo ./svc.sh status
EOF
