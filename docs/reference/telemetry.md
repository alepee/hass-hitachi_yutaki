# Telemetry

## Why?

This integration can collect anonymous performance data to:

- **Ensure stability** — detect regressions and validate fixes across all heat pump models and configurations.
- **Optimize energy consumption** — build realistic datasets that feed future energy-saving features while maintaining comfort.

## What is collected?

No personal information is ever collected. All data is identified by a non-reversible hash — there is no way to trace it back to you or your Home Assistant instance.

| Setting | Data | Frequency |
|---------|------|-----------|
| **Off** | Nothing | — |
| **On** | Installation info (model, gateway type, configuration) + fine-grained metrics (temperatures, compressor frequency, power consumption) + a one-time register snapshot | Metrics every 5 min; installation info re-sent once per day; snapshot once after opt-in |

## Identities

Every payload carries two non-reversible SHA-256 hashes:

- `instance_hash`: a hash of the Home Assistant instance id. One per **household**: every Hitachi config entry on the same HA instance shares it.
- `device_hash`: a hash of `f"{instance_id}:{entry.unique_id}"`, where `entry.unique_id` derives from the gateway hardware identifier. One per **heat-pump unit**.

The ingestion endpoint rate-limits at 1 request per 60 seconds per `(device_hash, payload_type)`. An installation with several Hitachi gateways therefore gets one independent rate-limit budget per unit instead of sharing a single one, so no unit's flushes are starved by another's. A payload sent without `device_hash` (older client versions) falls back to the instance identity for backward compatibility, matching the pre-#395 behavior.

## Buffering and retries

Data points are buffered locally and sent every 5 minutes. If a send fails, its points go back into the buffer and are retried on the next cycle, so a short network outage no longer loses them. Two bounds keep that safe:

- Points older than 30 minutes are discarded: stale data has no analytical value, and a misreading unit cannot keep replaying it.
- One request carries at most 80 points, so a backlog drains over several cycles instead of growing into a request the ingestion endpoint refuses. A batch refused as too large is dropped rather than retried, with a warning naming the config entry.

## How to enable or disable telemetry

Go to **Settings → Devices & Services → Hitachi Yutaki → Configure** and select the telemetry step. You can enable or disable telemetry at any time.

## Community discussion

See [Discussion #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200) for context and community feedback on this feature.
