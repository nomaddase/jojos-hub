#!/usr/bin/env bash
set -euo pipefail

# One-shot setup for GitHub Actions -> JoJo Hub autodeploy.
# Run as the normal runtime user (historically: admini), not as root.
# Prerequisite: `gh auth login` completed with access to nomaddase/jojos-hub.

REPO="nomaddase/jojos-hub"
LABEL="jojos-hub"
RUNTIME_USER="${JOJOS_USER:-admini}"
CHECKOUT="/home/${RUNTIME_USER}/jojos-monorepo"
RUNNER_DIR="/home/${RUNTIME_USER}/actions-runners/${LABEL}"

if [ "${EUID}" -eq 0 ]; then
  echo "Run this script as ${RUNTIME_USER}, not root. It will invoke sudo only where needed."
  exit 1
fi

if [ "$(id -un)" != "${RUNTIME_USER}" ]; then
  echo "Expected runtime user '${RUNTIME_USER}', got '$(id -un)'."
  echo "Override with JOJOS_USER only if the production service was intentionally changed."
  exit 1
fi

for cmd in curl git rsync python3 gh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing command: $cmd"
    exit 1
  fi
done

if [ ! -d "${CHECKOUT}/.git" ]; then
  echo "Missing checkout: ${CHECKOUT}"
  echo "Run deploy/bootstrap-fresh-ubuntu.sh first."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated. Run: gh auth login"
  exit 1
fi

# The workflow needs passwordless access only to these tightly scoped service diagnostics/actions.
SUDOERS_FILE="/etc/sudoers.d/jojos-github-runner"
TMP_SUDOERS="$(mktemp)"
cat >"${TMP_SUDOERS}" <<EOF
${RUNTIME_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl restart jojos-core.service
${RUNTIME_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl status jojos-core.service --no-pager
${RUNTIME_USER} ALL=(root) NOPASSWD: /usr/bin/journalctl -u jojos-core.service -n 100 --no-pager
EOF
sudo install -m 0440 "${TMP_SUDOERS}" "${SUDOERS_FILE}"
rm -f "${TMP_SUDOERS}"
sudo visudo -cf "${SUDOERS_FILE}"

TOKEN="$(gh api -X POST "repos/${REPO}/actions/runners/registration-token" --jq .token)"
GH_RUNNER_TOKEN="${TOKEN}" bash "${CHECKOUT}/deploy/register-runner.sh" "${REPO}" "${LABEL}"
unset TOKEN
unset GH_RUNNER_TOKEN

cd "${RUNNER_DIR}"

if ! sudo ./svc.sh status >/dev/null 2>&1; then
  sudo ./svc.sh install "${RUNTIME_USER}"
fi
sudo ./svc.sh start
sudo ./svc.sh status

printf '\nAutodeploy runner is configured.\n'
printf 'Repository: %s\n' "${REPO}"
printf 'Runner label: %s\n' "${LABEL}"
printf 'Workflow: .github/workflows/deploy-hub.yml\n'
printf 'Next: trigger workflow_dispatch or push a deployable change to main.\n'
