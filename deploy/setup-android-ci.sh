#!/usr/bin/env bash
set -euo pipefail

RUNTIME_USER="${JOJOS_USER:-admini}"
CHECKOUT="/home/${RUNTIME_USER}/jojos-monorepo"
SIGN_DIR="/home/${RUNTIME_USER}/.config/jojos-android"
KEYSTORE="${SIGN_DIR}/debug.keystore"
SECRET_NAME="ANDROID_DEBUG_KEYSTORE_BASE64"

if [ "${EUID}" -eq 0 ]; then
  echo "Run this script as ${RUNTIME_USER}, not root."
  exit 1
fi

if [ "$(id -un)" != "${RUNTIME_USER}" ]; then
  echo "Expected user ${RUNTIME_USER}, got $(id -un)."
  exit 1
fi

for cmd in gh curl python3 base64; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing command: $cmd"
    exit 1
  fi
done

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated for ${RUNTIME_USER}. Run: gh auth login"
  exit 1
fi

if [ ! -x "$(command -v keytool || true)" ]; then
  echo "Installing Java keytool..."
  sudo apt-get update
  sudo apt-get install -y openjdk-17-jre-headless
fi

mkdir -p "${SIGN_DIR}"
chmod 700 "${SIGN_DIR}"

if [ ! -f "${KEYSTORE}" ]; then
  echo "Creating persistent JoJo Android debug signing key..."
  keytool -genkeypair \
    -keystore "${KEYSTORE}" \
    -storepass android \
    -alias androiddebugkey \
    -keypass android \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname "CN=JoJo Android Debug,O=JoJo,C=KZ" \
    -noprompt >/dev/null 2>&1
  chmod 600 "${KEYSTORE}"
else
  echo "Persistent Android signing key already exists; keeping it unchanged."
fi

set_secret() {
  local repo="$1"
  echo "Updating ${SECRET_NAME} in ${repo}..."
  base64 -w0 "${KEYSTORE}" | gh secret set "${SECRET_NAME}" --repo "${repo}"
}

register_runner() {
  local repo="$1"
  local label="$2"
  local dir="/home/${RUNTIME_USER}/actions-runners/${label}"

  echo
  echo "Configuring runner ${label} for ${repo}..."
  local token
  token="$(gh api -X POST "repos/${repo}/actions/runners/registration-token" --jq .token)"
  GH_RUNNER_TOKEN="${token}" bash "${CHECKOUT}/deploy/register-runner.sh" "${repo}" "${label}"
  unset token

  cd "${dir}"
  if [ ! -f .service ]; then
    sudo ./svc.sh install "${RUNTIME_USER}"
  fi
  sudo ./svc.sh start
  sudo ./svc.sh status
}

set_secret "nomaddase/jojos-kitchen"
set_secret "nomaddase/jojos-kso"

register_runner "nomaddase/jojos-kitchen" "jojos-kitchen"
register_runner "nomaddase/jojos-kso" "jojos-kso"

echo
echo "Triggering Android workflows..."
gh workflow run build-deploy.yml --repo nomaddase/jojos-kitchen --ref main || true
gh workflow run build-deploy.yml --repo nomaddase/jojos-kso --ref main || true

echo
echo "Android CI setup complete."
echo "Kitchen runner: /home/${RUNTIME_USER}/actions-runners/jojos-kitchen"
echo "KSO runner:     /home/${RUNTIME_USER}/actions-runners/jojos-kso"
echo "Signing key:   ${KEYSTORE}"
echo "The private key was not printed and was not committed to Git."
