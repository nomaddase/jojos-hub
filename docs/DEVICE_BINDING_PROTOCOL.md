# Android device ↔ physical Hub binding

## Goal

KSO and Kitchen devices may be physically moved between stores. Every store intentionally uses the same Wi-Fi SSID and the same Hub LAN address, so SSID/IP must never be treated as store identity.

A physical Hub is identified by its immutable `installation_id`. Central `hub_id` and `store_id` are metadata attached to that installation and may be assigned later or changed administratively.

## Device identity

Each Android installation generates and persists one random UUID `device_id` on first launch. App updates preserve it. A full uninstall/factory reset may create a new identity.

Recommended role-prefixed IDs:

- `kso-<uuid>`
- `kitchen-<uuid>`

## Binding

Before opening normal runtime UI, call:

`POST /api/devices/bind`

Example request:

```json
{
  "device_id": "kso-8d11...",
  "app_role": "kso",
  "version_code": 12,
  "version_name": "1.2.0",
  "android_version": "14",
  "model": "...",
  "manufacturer": "...",
  "build_fingerprint": "...",
  "previous_hub_installation_id": "optional-old-id"
}
```

Example response:

```json
{
  "status": "ok",
  "device_id": "kso-8d11...",
  "app_role": "kso",
  "hub_installation_id": "immutable-physical-hub-id",
  "hub_id": "central-base-hub-id-or-null",
  "store_id": "central-store-id-or-null",
  "hub_status": "active",
  "binding_id": "per-device-per-hub-binding-id",
  "rebound": false,
  "heartbeat_interval_seconds": 30
}
```

Store `hub_installation_id` and `binding_id` locally and include both in every heartbeat.

## Automatic move to another store

At another store the Android device reconnects to the same Wi-Fi and same `192.168.50.1`, but `/api/devices/bind` returns a different `hub_installation_id`.

When that happens the application must:

1. stop all streams/requests associated with old runtime state;
2. discard Hub-derived caches;
3. for KSO also clear cart/configurator/service mode and any unsent guest order state;
4. persist the new `hub_installation_id` and `binding_id`;
5. fetch current Hub settings/catalog/order state;
6. resume only with data from the new Hub.

This is automatic and does not require editing a store ID on the Android device.

## Heartbeat enforcement

`POST /api/devices/heartbeat` accepts `hub_installation_id` and `binding_id`.

A mismatch may return HTTP 409 with `hub_rebind_required` or `device_binding_required`. Android clients must call `/api/devices/bind` again and perform the same old-state cleanup before retrying.

## Identity endpoint

`GET /api/hub/identity` exposes the current physical `installation_id` plus central `hub_id`, `store_id`, and Hub status. It contains no credentials.
