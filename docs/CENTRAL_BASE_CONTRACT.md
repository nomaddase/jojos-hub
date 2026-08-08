# JoJo Hub <-> JoJo Base relationship

Central system repository: `nomaddase/jojos-base`.

## Identity

A hub does not own its permanent corporate identity.

On first successful enrollment with JoJo Base:
- the hub presents a locally generated `installation_id` and device identity;
- Base issues a permanent UUID `hub_id` and per-hub credentials;
- the hub stores them locally;
- Base initially marks the hub pending/unassigned;
- an administrator binds the hub to a sales point in Base;
- reassigning a hub later does not change its `hub_id`.

If the OS is wiped and hub identity files are not restored, the installation is treated as a new hub and receives a new `hub_id`.

## Base authoritative data

The hub receives and caches:
- assigned store identity;
- catalog/products/groups;
- options/modifiers;
- components;
- active BOM/recipe versions;
- prices/availability;
- store/global settings;
- inventory bootstrap/reconciliation data;
- inbound transfers.

The hub must continue running on the last valid cached revision while Base/Internet is unavailable.

## Hub outbound data

Operational events are persisted to a durable local outbox before network transmission.

Examples:
- order created/status changes;
- component consumption;
- inventory count/observation;
- transfer receipt confirmation;
- health/version information;
- later device/printer diagnostics.

Every event has a globally unique `event_id`. Base acknowledgements make retries idempotent; the hub deletes/marks an outbox event delivered only after acknowledgement.

## Sync behavior

- Heartbeat is lightweight and frequent enough for fleet monitoring.
- Configuration/catalog sync is revision-based, not full-download on every heartbeat.
- Full bootstrap is used for first assignment or when incremental history cannot be used.
- Applying a Base revision locally should be transactional.
- Order flow/Kitchen/KSO must not depend on WAN latency.

Detailed central protocol is maintained in `jojos-base/docs/HUB_PROTOCOL.md`.
