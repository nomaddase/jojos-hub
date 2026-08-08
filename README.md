# JoJo Hub

Local store runtime and single source of truth for a JoJo point.

## Repositories

- `nomaddase/jojos-hub` — FastAPI/SQLite hub runtime and temporary legacy React fallback UI.
- `nomaddase/jojos-kso` — native Android KSO application.
- `nomaddase/jojos-kitchen` — native Android Kitchen application.

The hub owns catalog validation, prices, inventory checks, order creation/status transitions, ETA, printing, settings, media and synchronization. Android applications are clients of the hub and must not duplicate authoritative business rules.

## Production paths

- Runtime: `/home/admini/jojos-core`
- Repository checkout: `/home/admini/jojos-monorepo`
- Backups: `/home/admini/jojos-backups/hub`
- KSO APK releases: `/home/admini/jojos-releases/kso`
- Kitchen APK releases: `/home/admini/jojos-releases/kitchen`
- Service: `jojos-core.service`
- API listen address: `0.0.0.0:8080`

## Fresh OS recovery

Start with `docs/RECOVERY_STATE_2026-08-08.md` and then run:

```bash
sudo bash deploy/bootstrap-fresh-ubuntu.sh
```

The bootstrap intentionally does not contain passwords, GitHub tokens, Wi-Fi PSKs, signing keys or other secrets.

## Important runtime defaults

- Languages: `ru`, `kz`, `en`
- Default language: `ru`
- KSO idle timeout: `15s` (runtime override supported)
- Kitchen warning ratio: `0.7`
- Ready-order display visibility: `300s`
- Service modes: `dine_in`, `takeaway`
- Fixed label size: `58x40 mm`
- Printer default: `192.168.0.240:9100`

## Core event model

Kitchen and Display use Server-Sent Events:

- `GET /api/events/kitchen`
- `GET /api/events/display`

The streams emit update events and heartbeats. Clients must reconnect on transient failures and must not reload the entire screen on healthy heartbeat traffic.

## Deployment

`main` is the production branch. GitHub Actions deploys the hub through a self-hosted runner on the store hub. The workflow backs up runtime state, deploys source, rebuilds the legacy fallback UI, restarts `jojos-core.service`, then checks `/api/health`.
