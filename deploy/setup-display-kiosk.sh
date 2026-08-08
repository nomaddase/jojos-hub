#!/usr/bin/env bash
set -euo pipefail

# Configure the monitor physically connected to the Hub as the public order-status display.
# Creates a dedicated graphical account and starts /display in browser kiosk mode after every boot.
# Run as root: sudo bash deploy/setup-display-kiosk.sh

DISPLAY_USER="${JOJOS_DISPLAY_USER:-jojos-display}"
DISPLAY_URL="${JOJOS_DISPLAY_URL:-http://127.0.0.1:8080/display}"
SESSION_NAME="jojos-display"
SESSION_SCRIPT="/usr/local/bin/jojos-display-session"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf.d/50-jojos-display.conf"

if [ "${EUID}" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/setup-display-kiosk.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  lightdm lightdm-gtk-greeter openbox \
  x11-xserver-utils unclutter curl dbus-x11

# Ubuntu commonly provides Firefox as the supported browser package (often backed by snap).
# Prefer an already-installed Chromium/Chrome, otherwise ensure Firefox is available.
if ! command -v chromium >/dev/null 2>&1 \
  && ! command -v chromium-browser >/dev/null 2>&1 \
  && ! command -v google-chrome-stable >/dev/null 2>&1 \
  && ! command -v firefox >/dev/null 2>&1; then
  apt-get install -y firefox || true
fi

if ! command -v chromium >/dev/null 2>&1 \
  && ! command -v chromium-browser >/dev/null 2>&1 \
  && ! command -v google-chrome-stable >/dev/null 2>&1 \
  && ! command -v firefox >/dev/null 2>&1; then
  echo "No supported kiosk browser was found after installation."
  exit 1
fi

if ! id "${DISPLAY_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${DISPLAY_USER}"
fi

usermod -aG video,audio,input "${DISPLAY_USER}" || true
passwd -l "${DISPLAY_USER}" >/dev/null 2>&1 || true

install -d -m 0755 /etc/lightdm/lightdm.conf.d
install -d -m 0755 /usr/share/xsessions

cat >"${SESSION_SCRIPT}" <<EOF
#!/usr/bin/env bash
set -u

DISPLAY_URL="${DISPLAY_URL}"

# Do not blank, suspend or power off the directly connected order-status monitor.
xset s off || true
xset s noblank || true
xset -dpms || true
unclutter -idle 0.5 -root >/dev/null 2>&1 &

# Keep a minimal window manager alive for the browser window.
openbox --config-file /etc/xdg/openbox/rc.xml >/tmp/jojos-display-openbox.log 2>&1 &

# Wait until the local Hub API/UI is healthy before opening the board.
until curl -fsS --max-time 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1; do
  sleep 1
done

pick_browser() {
  if command -v chromium >/dev/null 2>&1; then echo chromium; return; fi
  if command -v chromium-browser >/dev/null 2>&1; then echo chromium-browser; return; fi
  if command -v google-chrome-stable >/dev/null 2>&1; then echo google-chrome-stable; return; fi
  if command -v firefox >/dev/null 2>&1; then echo firefox; return; fi
  return 1
}

while true; do
  BROWSER="\$(pick_browser)" || { sleep 5; continue; }

  case "\${BROWSER}" in
    firefox)
      MOZ_ENABLE_WAYLAND=0 "\${BROWSER}" --kiosk "\${DISPLAY_URL}" >/tmp/jojos-display-browser.log 2>&1 || true
      ;;
    *)
      "\${BROWSER}" \
        --kiosk \
        --no-first-run \
        --disable-session-crashed-bubble \
        --disable-infobars \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        "\${DISPLAY_URL}" >/tmp/jojos-display-browser.log 2>&1 || true
      ;;
  esac

  # If the browser crashes or is closed, bring the board back automatically.
  sleep 2
done
EOF
chmod 0755 "${SESSION_SCRIPT}"

cat >"/usr/share/xsessions/${SESSION_NAME}.desktop" <<EOF
[Desktop Entry]
Name=JoJo Order Display
Comment=JoJo customer order status board
Exec=${SESSION_SCRIPT}
Type=Application
DesktopNames=JoJoDisplay
EOF

cat >"${LIGHTDM_CONF}" <<EOF
[Seat:*]
autologin-user=${DISPLAY_USER}
autologin-user-timeout=0
user-session=${SESSION_NAME}
greeter-session=lightdm-gtk-greeter
allow-guest=false
greeter-hide-users=true
EOF

# Prevent the kiosk account from being used as a normal SSH/password account.
install -d -m 0755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/98-jojos-display.conf <<EOF
DenyUsers ${DISPLAY_USER}
EOF
sshd -t
systemctl reload ssh || systemctl reload sshd || true

systemctl set-default graphical.target
systemctl enable lightdm.service
systemctl restart lightdm.service

echo "JoJo public order display is configured."
echo "Display account: ${DISPLAY_USER}"
echo "Display URL:     ${DISPLAY_URL}"
echo "It will auto-login and reopen the board after every Hub reboot."
