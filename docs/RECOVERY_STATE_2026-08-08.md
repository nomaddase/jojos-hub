# JoJo Hub recovery state — 2026-08-08

This file captures the recoverable architecture and runtime decisions before the store hub OS reinstall.

## Known machine identity

- Linux account used by the runtime: `admini`
- Hostname observed in shell: `jojos`
- Runtime root: `/home/admini/jojos-core`
- Frontend working tree used during development: `/home/admini/jojos-ui`
- Combined checkout used during deployment work: `/home/admini/jojos-monorepo`
- Python virtualenv: `/home/admini/jojos-core/venv`
- Backend port: `8080`

Passwords, Wi-Fi PSKs, GitHub tokens and signing credentials are not recoverable from the repository and are intentionally not reconstructed here.

## Repository split

Production direction:

1. `jojos-hub` — local backend, DB, printing, sync and temporary browser fallback.
2. `jojos-kso` — native Android KSO APK, Kotlin + Jetpack Compose, no WebView.
3. `jojos-kitchen` — native Android Kitchen APK, Kotlin + Jetpack Compose, no WebView.

A future Display native app can be split similarly. Until then the legacy browser Display remains a fallback.

## Hub responsibilities

The hub is the local store source of truth and must continue operating without Internet access. It owns:

- catalog and option validation;
- authoritative product/option prices;
- inventory checks/decrement;
- order creation and state transitions;
- ETA computation;
- Kitchen/Display event snapshots;
- runtime settings;
- media/catalog cache;
- printing jobs;
- central synchronization and later durable retry/outbox work.

Clients must not be trusted for names, prices, preparation times or valid option combinations.

## Runtime defaults

- languages: `ru`, `kz`, `en`
- default language: `ru`
- KSO idle timeout: `15 seconds`
- kitchen warning ratio: `0.7`
- display ready visibility: `300 seconds`
- service modes: `dine_in`, `takeaway`
- default service mode: `dine_in`

Runtime settings override defaults where supported.

## Main API surface known before reinstall

Health:

- `GET /health`
- `GET /api/health`

Catalog/settings/inventory/media:

- `GET /api/catalog`
- `GET /api/settings`
- inventory and media routers under `/api/...`

Orders:

- `POST /api/orders`
- `GET /api/orders`
- `GET /api/orders/{order_id}`
- `POST /api/orders/{order_id}/ready`
- `POST /api/orders/{order_id}/cancel`
- `GET /api/orders/eta/current`
- `POST /api/orders/eta/preview`

Kitchen/Display:

- `GET /api/kitchen/orders`
- `GET /api/display/orders`
- `GET /api/events/kitchen`
- `GET /api/events/display`

Printing:

- `POST /api/printing/orders/{order_id}/label`
- `GET /api/printing/orders/{order_id}/jobs`

Analytics known endpoint:

- `GET /api/analytics/kitchen/daily`

Legacy aliases existed for older clients where required.

## SSE behavior

Kitchen and Display moved from visible polling churn to Server-Sent Events.

Expected behavior:

- first compact snapshot on connect;
- update event only when revision changes;
- periodic `heartbeat` events;
- client does not close EventSource on first transient error;
- fallback polling is allowed only when the event stream is genuinely unhealthy;
- no full-screen page reload for ordinary updates.

Before the native migration, `/api/events/kitchen` was verified to emit `kitchen_update` plus repeated `heartbeat` events correctly.

## Kitchen behavior to preserve in native APK

- board of active orders;
- large order number;
- clear `В зале` / strongly highlighted `С собой`;
- complete item composition;
- modifiers/add-ons shown under each item;
- target preparation time;
- smooth timer updated locally once per second;
- timer basis: `accepted_at` when present, otherwise `created_at`;
- incoming order updates must never reset existing timers;
- stable selected-order side panel;
- Ready action;
- hold-to-cancel action;
- warning state around configured ratio;
- overdue state after target time;
- SSE reconnect without page recreation.

The browser Kitchen worked correctly enough to prove the backend/event path; Android WebView reload/watchdog behavior was the reason for moving Kitchen to native.

## KSO behavior to preserve in native APK

- attract screen;
- RU/KAZ/EN selector;
- `Начать заказ`;
- choose `В зале` or `С собой`;
- catalog groups and products;
- fullscreen/stable configurator;
- `single` option group: one choice, free;
- `multi` option group: first option actually selected by the guest is free, later selected options use their configured price;
- no UI geometry jump when price labels change;
- cart and checkout;
- upsell only in checkout; recommendations from other product groups not already represented in the order, simple one-tap products preferred;
- ETA shown in ordering flow;
- success screen with order number;
- idle reset defaults to 15 seconds;
- hub remains authoritative for all price/catalog/inventory validation.

## Display fallback behavior

- two zones: preparing and ready;
- large readable order numbers;
- adaptive 2–3 cards per row;
- automatic pagination only when capacity is exceeded;
- no manual scrolling requirement;
- ready orders disappear after configured timeout.

## Printing

- fixed network label printer endpoint default: `192.168.0.240:9100`;
- label size: `58x40 mm`;
- printing remains a hub responsibility, not an Android responsibility;
- transport currently uses raw TCP socket adapter;
- printing is split into service/template/adapter modules;
- `print_jobs` are persisted;
- exact vendor dialect may still need physical-printer tuning (TSPL/ZPL/EPL depending on actual model).

## Data and backup rules

Do not overwrite during deploy:

- `jojos_core.db`
- `config/`
- `data/`
- `static/` except when deliberately rebuilding the fallback web UI
- Python `venv/`

Back up DB/config/data before production deploy.

## Service model after reinstall

Use systemd, not ad-hoc `nohup`/`pkill` runtime management.

Service file lives at:

`deploy/systemd/jojos-core.service`

Expected command:

`/home/admini/jojos-core/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080`

## GitHub deployment topology

- push/merge to `jojos-hub/main` -> self-hosted runner on hub -> backup -> deploy -> restart -> health check;
- push/merge to `jojos-kso/main` -> GitHub-hosted Android build -> APK artifact -> hub runner copies latest APK to `/home/admini/jojos-releases/kso/`;
- push/merge to `jojos-kitchen/main` -> GitHub-hosted Android build -> APK artifact -> hub runner copies latest APK to `/home/admini/jojos-releases/kitchen/`.

Silent installation from hub to Android devices is a separate later stage. During early debugging APK delivery to the hub is automated, while device installation remains controlled.

## Central synchronization direction

Planned central contracts included concepts equivalent to:

- store bootstrap;
- store settings;
- catalog;
- inventory;
- media;
- upsell rules;
- order import;
- kitchen daily analytics;
- hub heartbeat.

Pull-style data should carry version/checksum/updated-at metadata. Orders/analytics sent centrally should become idempotent and durable before multi-store rollout.

## Production gaps intentionally still open

Do not mistake these for recovered completed features:

- explicit DB migration/versioning beyond additive startup migration;
- durable central outbox/retry/dead-letter flow;
- final LAN/API device authentication model;
- SQLite concurrency hardening/WAL/busy-timeout validation under simultaneous KSO traffic;
- cancellation inventory-restock policy confirmation;
- unique production order-number policy verification under same-second concurrent orders;
- physical printer protocol validation;
- silent Android device-owner update mechanism;
- final central management UI.
