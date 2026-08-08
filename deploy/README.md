# JoJo deployment topology

Production deployment uses GitHub Actions with self-hosted runners installed on the store hub.

Repositories:
- `nomaddase/jojos-hub` -> FastAPI/SQLite hub runtime
- `nomaddase/jojos-kso` -> native Android KSO APK
- `nomaddase/jojos-kitchen` -> native Android Kitchen APK

Hub paths:
- backend runtime: `/home/admini/jojos-core`
- hub backups: `/home/admini/jojos-backups/hub`
- KSO APK releases: `/home/admini/jojos-releases/kso`
- Kitchen APK releases: `/home/admini/jojos-releases/kitchen`

Self-hosted runner labels:
- Hub repo runner: `jojos-hub`
- KSO repo runner: `jojos-kso`
- Kitchen repo runner: `jojos-kitchen`

The hub backend deploy workflow preserves runtime state (`jojos_core.db`, `config/`, `data/`, `static/`) and replaces source code before restarting the system-level `jojos-core.service`. During the native migration it also rebuilds `jojos-ui` as a legacy fallback.

Android repositories build APKs on GitHub-hosted Ubuntu runners. Their deploy jobs run on the hub and place the built APK into the release directories above. Device-side silent update is deliberately separate from artifact delivery to the hub and will be added after the native apps and device-management contract are stable.
