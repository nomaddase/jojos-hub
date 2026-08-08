# JoJo Hub — Native Android Production Architecture

## Goal

Migrate all operational device UIs from browser/WebView HTML pages to native Android APK applications while keeping `jojos-core` as the single local source of truth for the store.

The existing React/Vite frontend remains temporarily as a fallback during migration and is removed only after the native apps pass production QA.

## Repository target structure

```text
jojos-hub/
├── jojos-core/                     # FastAPI + SQLite local store hub
├── jojos-ui/                       # legacy web UI, temporary fallback during migration
├── jojos-android/                  # one Gradle project, three production APKs
│   ├── app-kso/                    # customer kiosk APK
│   ├── app-kitchen/                # kitchen staff APK
│   ├── app-display/                # public order-status APK
│   ├── core-model/                 # shared API/domain models
│   ├── core-network/               # HTTP, SSE, discovery, connection state
│   ├── core-ui/                    # shared Compose theme/components
│   └── core-device/                # device identity, hub discovery, startup/device helpers
└── .github/workflows/
    └── android-build.yml           # build/test all APKs and publish artifacts
```

## Android stack

- Kotlin
- Jetpack Compose
- Material 3 primitives only; screens must use custom JoJo visual design rather than generic Material layouts
- Coroutines / StateFlow
- OkHttp for HTTP
- OkHttp SSE/EventSource for realtime kitchen/display updates
- kotlinx.serialization for JSON
- DataStore for small local device configuration
- no embedded WebView for business screens
- no business logic duplicated in APKs

The APKs are presentation clients. Core business rules remain in `jojos-core`.

## Core architecture

`jojos-core` remains the local authority for:

- client/store identity
- settings
- catalog
- inventory
- media metadata
- orders
- order lifecycle
- preparation timing
- ETA
- kitchen analytics
- printing
- central synchronization

The Android clients must never call the central system directly.

## Device roles

Every APK has a fixed application role:

- `kso`
- `kitchen`
- `display`

On first start the application obtains a stable Android device identifier, discovers the local JoJo hub, registers itself with the hub, and receives its runtime configuration.

Proposed endpoints:

```text
POST /api/devices/register
GET  /api/devices/{device_id}/config
POST /api/devices/{device_id}/heartbeat
```

Registration should include at minimum:

```json
{
  "device_id": "stable-device-id",
  "role": "kso|kitchen|display",
  "app_version": "x.y.z",
  "platform": "android",
  "model": "..."
}
```

The hub stores the device and returns the effective store/device settings.

## Hub discovery

Preferred production discovery order:

1. cached last successful hub URL
2. mDNS service `_jojos-core._tcp.local`
3. fixed fallback `http://192.168.50.1:8080`
4. hidden/manual service screen for commissioning only

The goal is that a provisioned KSO/Kitchen/Display device can be powered on and automatically connect to the hub on the store LAN.

## Connection model

### KSO

KSO uses REST for catalog/order operations and a lightweight connection monitor.

Required APIs:

```text
GET  /api/health
GET  /api/settings
GET  /api/catalog
GET  /api/orders/eta/current
POST /api/orders/eta/preview
POST /api/orders
```

### Kitchen

Kitchen uses SSE as the primary realtime transport.

```text
GET /api/events/kitchen
```

SSE events must include server time/revision metadata so the native timer does not depend on browser date parsing or remount behavior.

Recommended event envelope:

```json
{
  "revision": "...",
  "server_time_ms": 1780000000000,
  "payload": []
}
```

The native app maintains a single local `StateFlow<List<KitchenOrder>>` and only mutates entries whose revision/data changed.

Timers are rendered natively from a monotonic ticker and a server clock offset. They must never reset because a network update arrived.

### Display

Display uses SSE as the primary realtime transport.

```text
GET /api/events/display
```

The app renders accepted and ready orders using native Compose layout. It uses adaptive density and automatic pagination; no manual scroll is required during normal operation.

## KSO APK requirements

Native KSO must implement:

1. attract screen
2. language choice (default RU/KAZ/EN, settings driven)
3. start order
4. dine-in / takeaway choice
5. catalog categories
6. product cards with images, price and prep estimate
7. product configurator
8. option logic
9. cart
10. checkout upsell
11. ETA
12. create order
13. success screen
14. automatic reset after configured timeout

Option rules remain server-authoritative:

- single group: one choice
- multi group: first user-selected option is free, later options are paid
- backend validates catalog IDs and authoritative prices

After successful order creation, the success screen should return to the attract screen after 15 seconds by default (settings override supported).

## Kitchen APK requirements

Native Kitchen must implement:

- realtime SSE order updates
- no periodic page refresh architecture
- local timer updated every second
- card list/grid with scrolling
- full order composition
- modifiers/options
- clear takeaway highlight
- target preparation time
- warning / overdue states
- selected order side/detail panel
- ready action
- hold-to-cancel action
- connection indicator only after a real sustained transport outage
- automatic SSE reconnect with exponential backoff

No WebView reload or polling-based visual refresh is allowed.

## Display APK requirements

Native Display must implement:

- Accepted zone
- Ready zone
- very large order numbers
- 2–3 cards per row depending on display size/load
- adaptive density
- automatic pagination when capacity is exceeded
- no manual scrolling in normal operation
- ready orders removed according to core setting
- automatic SSE reconnect

## Printing

Printing remains a `jojos-core` responsibility, not an APK responsibility.

The production label printer is fixed on the store network and uses 58x40 mm labels.

Keep:

```text
jojos-core/app/modules/printing/
```

The core owns:

- label DTO
- label template
- printer adapter/protocol
- fixed printer network endpoint
- print job audit/retry

Android applications only display order/print state if needed; they do not open raw printer sockets.

## Local/offline behavior

Loss of internet to the central system must not stop store operation.

Loss of LAN connection between an APK and the hub must:

- keep the current screen/state visible
- show a non-destructive connection indicator after a grace period
- reconnect automatically
- never reload/reset an active order interaction

KSO must not submit a new order while disconnected unless an explicit offline order queue is implemented later.

## Core changes required for native clients

1. Device registration/config API
2. mDNS advertisement of the local hub
3. API version endpoint
4. server-time/revision metadata in realtime streams
5. typed API contracts for Android models
6. stable error envelope
7. authentication/device token boundary for store LAN clients
8. CORS/web-static behavior may remain during migration but is no longer the primary client path

Recommended API metadata:

```text
GET /api/version
GET /api/health
```

Example stable error body:

```json
{
  "error": {
    "code": "ORDER_ALREADY_FINAL",
    "message": "Order is already ready or cancelled",
    "details": {}
  }
}
```

## Android lifecycle / kiosk behavior

Apps should support:

- immersive fullscreen
- keep-screen-on
- orientation locking per app role
- reconnect after network loss
- resume without state destruction
- optional boot receiver/autostart where device policy allows

Manufacturer/device-owner kiosk policy remains preferred for true production lockdown.

## GitHub CI/CD

Add GitHub Actions to:

- run Python compile/tests for core
- run Android unit tests
- assemble debug APKs for all three apps on every PR
- assemble signed release APKs on release tag when secrets are configured
- upload APK artifacts:
  - `jojos-kso.apk`
  - `jojos-kitchen.apk`
  - `jojos-display.apk`

Do not commit signing keys to the repository.

## Migration sequence

### Phase 1 — foundation

- add Android multi-module project
- add shared model/network/device modules
- add core device registration/discovery/server-time support
- keep React UI operational

### Phase 2 — Kitchen first

Kitchen is migrated first because the current WebView/browser lifecycle is the known production problem.

Acceptance criteria:

- order composition correct
- timer ticks smoothly every second
- SSE updates do not reset timer or selected order
- no false disconnected flash
- ready/cancel stable

### Phase 3 — Display

Replace public web display with native APK and validate adaptive paging.

### Phase 4 — KSO

Port the already-working KSO business flow to Compose while preserving all backend validation and settings-driven behavior.

### Phase 5 — cutover

After all APKs pass QA:

- make native applications the official clients
- keep `jojos-ui` for one rollback release
- then archive/remove the legacy operational web UI

## Production rule

Do not patch around WebView behavior anymore. All operational screens are native APKs. `jojos-core` remains the only business-logic and state authority.
