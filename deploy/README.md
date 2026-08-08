# JoJo deployment topology

Production deployment uses GitHub Actions with self-hosted runners installed on the store hub.

Repositories:
- `nomaddase/jojos-hub` -> FastAPI/SQLite hub runtime
- `nomaddase/jojos-kso` -> native Android KSO APK
- `nomaddase/jojos-kitchen` -> native Android Kitchen APK

Hub paths:
- repository checkout: `/home/admini/jojos-monorepo`
- backend runtime: `/home/admini/jojos-core`
- legacy UI working tree: `/home/admini/jojos-ui`
- hub backups: `/home/admini/jojos-backups/hub`
- KSO APK releases: `/home/admini/jojos-releases/kso`
- Kitchen APK releases: `/home/admini/jojos-releases/kitchen`

Self-hosted runner labels:
- Hub repo runner: `jojos-hub`
- KSO repo runner: `jojos-kso`
- Kitchen repo runner: `jojos-kitchen`

## Fresh OS

The expected runtime account is `admini`; the historical hostname is `jojos`.

After cloning this repository on a fresh Ubuntu installation, run:

```bash
sudo bash deploy/bootstrap-fresh-ubuntu.sh
```

The script installs system packages, restores source from GitHub, creates the Python venv, builds the legacy fallback UI, installs/enables `jojos-core.service`, starts the service and checks `/api/health`.

## Wi-Fi hotspot

The old Wi-Fi credentials are intentionally not stored or reconstructed. Create a new password and keep it outside Git.

The historical store LAN was in the `192.168.50.0/24` range, so the helper defaults the hub to `192.168.50.1/24` but allows an override.

```bash
sudo \
  JOJOS_WIFI_SSID='YOUR-SSID' \
  JOJOS_WIFI_PASSWORD='YOUR-NEW-STRONG-PASSWORD' \
  bash deploy/setup-hotspot.sh
```

Do not commit the actual PSK.

## Core deployment

The hub backend deploy workflow preserves runtime state (`jojos_core.db`, `config/`, `data/`) and replaces source code before restarting the system-level `jojos-core.service`. During the native migration it also rebuilds `jojos-ui` as a legacy fallback.

## Android deployment

Android repositories build APKs on GitHub-hosted Ubuntu runners. Their deploy jobs run on the hub and place the built APK into the release directories above. Device-side silent update is deliberately separate from artifact delivery to the hub and will be added after the native apps and device-management contract are stable.

## Runner registration

Use `deploy/register-runner.sh` with a short-lived GitHub registration token. Never store that token in the repository. Each repository gets its own runner registration on the same physical hub with the label listed above.
