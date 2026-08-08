# Codex Task — Native Android Migration

Work only on branch `native-apps-rework`.

## Objective

Replace operational WebView/browser UIs with native Android APKs while preserving `jojos-core` as the single local business/state authority.

Do not remove `jojos-ui` yet. It remains rollback/fallback until native acceptance testing is complete.

Read `NATIVE_ARCHITECTURE.md` before changing code.

## Phase 1 — Core/native foundation

Implement the following in one reviewable pass.

### A. Android multi-module project

Create `jojos-android/` with modules:

- `app-kso`
- `app-kitchen`
- `app-display`
- `core-model`
- `core-network`
- `core-ui`
- `core-device`

Use:

- Kotlin
- Jetpack Compose
- Coroutines + StateFlow
- OkHttp
- OkHttp SSE
- kotlinx.serialization
- DataStore

Do not use WebView for operational screens.

Create minimal buildable apps with role-specific launch screens and shared JoJo theme.

### B. Shared network layer

Implement:

- hub URL storage
- HTTP JSON client
- SSE client with automatic reconnect/backoff
- connection state model with grace period (no instant disconnected flash)
- stable error model

Do not poll kitchen/display as the primary transport.

### C. Device identity/discovery

Implement Android-side:

- stable device ID
- role (`kso`, `kitchen`, `display`)
- cached hub URL
- fixed fallback `http://192.168.50.1:8080`
- architecture point for mDNS discovery

Implement core-side APIs:

```text
POST /api/devices/register
GET  /api/devices/{device_id}/config
POST /api/devices/{device_id}/heartbeat
GET  /api/version
```

Persist registered devices in SQLite with additive startup migration.

### D. Realtime contract hardening

Update:

```text
GET /api/events/kitchen
GET /api/events/display
```

Every update event must include:

- revision
- `server_time_ms`
- payload

Heartbeat must include `server_time_ms`.

Keep existing web clients compatible during migration if practical.

### E. CI

Add `.github/workflows/android-build.yml`.

On PR/push to native branch:

- compile/test Python core
- run Android unit tests
- assemble all three debug APKs
- upload APK artifacts

APK artifact names:

- `jojos-kso-debug.apk`
- `jojos-kitchen-debug.apk`
- `jojos-display-debug.apk`

No signing keys in repository.

## Phase 2 — Native Kitchen (highest priority)

After Phase 1 builds, implement Kitchen fully before KSO/Display.

### Kitchen behavior

- connect to `/api/events/kitchen`
- no WebView
- no page reload model
- one `StateFlow<List<KitchenOrder>>`
- incremental/order-ID merge
- local native 1-second ticker
- use server clock offset + `accepted_at || created_at`
- order timer must never reset because an SSE snapshot arrived
- full item composition
- modifiers
- target prep time
- warning and overdue states
- strong takeaway visualization
- scrollable order grid/list
- selected order detail screen/panel
- ready action
- hold-to-cancel interaction
- sustained connection-loss banner only after grace period
- automatic reconnect without clearing screen state

### Native Kitchen acceptance criteria

1. Create order from existing KSO/web API.
2. Native Kitchen receives it without manual refresh.
3. Timer increments exactly every second.
4. Incoming second order does not reset existing timer.
5. Disconnect LAN for 3 seconds: no destructive reset.
6. Sustained disconnect: connection banner appears, existing orders stay visible.
7. Restore LAN: reconnect automatically.
8. Side/detail view stays open during incoming events.
9. Ready works exactly once; invalid repeat returns/handles 409.
10. Cancel-hold works exactly once.
11. Item modifiers are visible.

## Phase 3 — Native Display

Implement only after Kitchen acceptance criteria pass.

- SSE display stream
- accepted and ready zones
- large native order cards
- adaptive 2/3-column layout
- automatic pagination
- no manual scroll for normal public view

## Phase 4 — Native KSO

Port the existing working KSO business flow to Compose.

Preserve all backend-authoritative validation.

Native KSO requirements:

- attract screen
- languages
- service mode
- catalog
- product images
- product configuration
- first selected multi-option free behavior represented correctly
- cart
- checkout upsell
- ETA
- order submit
- success screen
- default 15-second post-order/reset behavior, settings overridable

## Printing

Do not move printing to Android.

58x40 printer remains owned by `jojos-core` and fixed network endpoint logic remains centralized in the printing module.

## Scope rules

- Do not remove or rewrite core business validation into Android.
- Do not make Android talk to the central cloud directly.
- Do not remove React UI until native apps pass QA.
- Do not add WebView as a shortcut.
- Keep changes modular and reviewable.

## Deliverables for each implementation pass

Return:

1. exact files changed
2. new modules/endpoints
3. DB migration behavior
4. build commands
5. APK artifact paths/names
6. manual QA steps
7. remaining limitations

Do not return only an audit. Implement code and ensure it builds in CI.
