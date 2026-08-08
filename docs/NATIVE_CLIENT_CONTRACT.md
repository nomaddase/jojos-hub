# Native Android client contract

This document records the current hub contract that native `jojos-kso` and `jojos-kitchen` clients should consume. The hub remains authoritative.

## Base URL

Store LAN example after fresh provisioning:

`http://192.168.50.1:8080`

The actual base URL must remain configurable/discoverable; do not permanently hardcode it into business logic.

## Health

`GET /api/health`

Expected service response identifies `jojos-core` and healthy status.

## Settings

`GET /api/settings`

Effective runtime settings historically include:

```json
{
  "languages": ["ru", "kz", "en"],
  "default_language": "ru",
  "idle_timeout_seconds": 15,
  "kitchen": {"warning_ratio": 0.7},
  "display": {"ready_visibility_seconds": 300},
  "service_modes": {
    "enabled": ["dine_in", "takeaway"],
    "default": "dine_in"
  }
}
```

The backend sanitizes these values. Android should consume effective settings and should not invent a competing authoritative configuration.

## Catalog

`GET /api/catalog`

Products contain IDs, names, price, preparation seconds, description, image URL and option groups. Option groups use `mode` values such as `single` and `multi` and contain option items with ID/name/price.

Important: the current catalog file in the repository is development/placeholder data. Native apps must be data-driven and must not encode those products into Kotlin.

## ETA

- `GET /api/orders/eta/current`
- `POST /api/orders/eta/preview`

KSO displays hub-calculated ETA; it does not own the queue algorithm.

## Create order

`POST /api/orders`

Current request model:

```json
{
  "source": "kso",
  "service_mode": "dine_in",
  "items": [
    {
      "item_id": "product-id",
      "name": "client display value",
      "qty": 1,
      "price": 0,
      "options": [
        {
          "group_id": "group-id",
          "option_id": "option-id",
          "name": "client display value",
          "price": 0
        }
      ]
    }
  ]
}
```

The submitted name/price fields are not trusted. The backend normalizes against the catalog and validates option groups/inventory before persisting.

## Order response shape used by Kitchen

An order response contains at least:

```json
{
  "id": "...",
  "number": "...",
  "source": "kso",
  "status": "in_progress",
  "created_at": "UTC ISO-8601",
  "accepted_at": "UTC ISO-8601 or null",
  "ready_at": null,
  "cancelled_at": null,
  "total": 0,
  "target_prep_seconds": 120,
  "contains_sandwich": false,
  "service_mode": "dine_in",
  "actual_prep_seconds": null,
  "is_overdue": false,
  "items": [
    {
      "item_id": "...",
      "name": "...",
      "display_name": "...",
      "qty": 1,
      "price": 0,
      "options": [],
      "modifier_lines": [],
      "full_item_text": "1 × Item"
    }
  ]
}
```

Kitchen should render `display_name`/`name`, quantity and modifier lines. Raw options remain available when a richer native presentation is needed.

## Kitchen snapshot

`GET /api/kitchen/orders`

Returns active orders (`created` / `in_progress`) ordered by creation time. The backend marks newly observed `created` orders as `in_progress` and sets `accepted_at` if needed.

Native timer start rule:

1. `accepted_at` when present;
2. otherwise `created_at`.

Do not drive a visible timer from repeated backend `elapsed_seconds` values. Use the timestamps to establish the start point and tick locally.

## Kitchen SSE

`GET /api/events/kitchen`

Media type: `text/event-stream`.

Update event:

```text
event: kitchen_update
data: {"revision":"sha1...","payload":[...]}
```

Heartbeat event:

```text
event: heartbeat
data: {}
```

The server currently evaluates the payload once per second, emits a full compact snapshot only when its revision changes, and otherwise emits a heartbeat. A client must keep the connection alive and reconnect on transient failure without recreating the whole screen.

## Kitchen transitions

- `POST /api/orders/{order_id}/ready`
- `POST /api/orders/{order_id}/cancel`

The hub enforces transition validity. Android must surface conflict/error state rather than assuming a transition succeeded.

## Display SSE

`GET /api/events/display`

Update event name: `display_update`; heartbeat contract matches Kitchen.

## Printing

Android does not print directly. Printing is owned by the hub:

- `POST /api/printing/orders/{order_id}/label`
- `GET /api/printing/orders/{order_id}/jobs`

Current label default is 58x40 mm and current network printer default is `192.168.0.240:9100`.

## Offline model

The hub is designed to remain operational without Internet. KSO/Kitchen communicate over the store LAN. Native apps may preserve transient UI state, but no Android client should become an independent source of truth for completed orders, pricing or inventory.
