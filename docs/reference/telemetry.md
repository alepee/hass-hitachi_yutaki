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

- Points older than 30 minutes are discarded: stale data has no analytical value, and a misreading unit cannot keep replaying it. The buffer holds exactly that same window, whatever the poll cadence, so the two bounds express one rule rather than two.
- One request is bounded in bytes, not in points: the batch is filled up to 180 KB of serialized body, measured on the oldest point, and never exceeds 80 points. A point carries one field per register plus the derived metrics, so its size is a property of the heat-pump profile, roughly 1.1 KB on the narrowest and 3 KB on the widest. A point count alone would therefore leave a margin that varies with the profile: 80 points of the widest measure about 233 KB against the endpoint's 256 KB limit. A wide profile now sends fewer points per request instead of an oversized body. A batch refused as too large is still dropped rather than retried, with a warning naming the config entry.
- A backlog is drained one request per cycle, plus one catch-up request 65 seconds later when a delivered batch left points behind; the endpoint accepts one request per minute per unit, so the catch-up sits just past that window and well before the next regular flush. On the widest profiles the byte budget lets one request carry fewer points than a 5-second poll produces in 5 minutes (about 52 to 56 against 60), so without the catch-up the buffer would slowly saturate and evict points. No catch-up follows a failed send: that backlog waits for the next cycle. On unload or restart, whatever a last single flush cannot carry is discarded and the count is logged.

Because a flush is capped, a poll faster than roughly 3.75 seconds would produce more points per cycle than one request can carry: the buffer would saturate and silently discard the surplus. Collection is therefore decimated to match, keeping one poll out of N so a cycle never produces more than a flush can send. The default 5-second interval, and anything slower, is unaffected and collects every poll. When the stride applies, it is logged once at setup. Any point a full buffer still evicts is counted and reported in the log, so the loss is never silent.

A batch the endpoint has almost certainly already stored is not re-queued. The endpoint commits its rate-limit slot only once a payload is durably archived and the window is shorter than the flush cycle, so a rate-limit rejection that follows an attempt of ours whose answer never arrived means that attempt landed. Re-queueing there would archive the same points twice.

## Fleet ping

The fleet ping is a separate feature from telemetry, with its own setting. Once a day, the integration sends one tiny anonymous payload per Home Assistant instance, so I know how many installations are active and which hardware they run. That's what lets me prioritize work, decide when an old Home Assistant version can be dropped, and follow how fast a release is adopted.

### What is sent

This is the complete payload:

```json
{
  "type": "ping",
  "integration_version": "2.2.0",
  "ha_version": "2026.10.1",
  "climate_zone": "Cfb",
  "units": [
    {
      "profile": "yutaki_s80",
      "gateway_type": "modbus_atw_mbs_02",
      "power_supply": "three",
      "has_dhw": true,
      "has_pool": false,
      "has_cooling": true,
      "max_circuits": 2,
      "has_secondary_compressor": true
    }
  ]
}
```

### What is not sent

- **No identifier**: no hash, no entry id, no serial number. Two pings from the same installation cannot be linked.
- **No location**: the Köppen climate zone is computed inside Home Assistant from its configured location, and only the zone leaves it.
- **No measurement**: no temperature, power, energy or register value.

The endpoint keeps nothing about the request itself: no IP address, no request log. It turns each unit of the ping into one anonymous counter row, and that's all.

### How often

At most once per UTC day per Home Assistant instance, whatever the number of Hitachi units and restarts. The day of the last delivered ping is stored locally (`.storage/hitachi_yutaki_fleet_ping`). The first attempt comes 10 minutes after Home Assistant starts, so every unit has been polled; a failed attempt is retried every hour. Counting the pings received on a day gives the number of active installations that day, without any identifier.

### Public stats

The aggregated results are public: [fleet stats](https://alepee.github.io/hass-hitachi_yutaki/fleet-stats.html), refreshed daily, raw data at `https://hitachi-telemetry.lepee.dev/v1/stats`. Each chart shows **one attribute on its own** (versions, climate zone, model, gateway, power supply, circuits, capabilities), never a combination of attributes, so no installation can be singled out.

### Consent

| | Telemetry | Fleet ping |
|---|---|---|
| Default | Off (opt-in) | **On (opt-out)** |
| Content | Fine-grained metrics, pseudonymous hashes | Anonymous installation profile, no identifier |

- **Telemetry On implies the fleet ping**: telemetry already shares a superset of this information.
- **Telemetry Off leaves the fleet ping on its own toggle.**
- A one-time repair notice presents the fleet ping and lets you turn it off. Afterwards, change it in **Settings → Devices & Services → Hitachi Yutaki → Configure**: the fleet ping step follows the telemetry step when telemetry is off.
- With several Hitachi units on one instance, the ping only lists the units whose entry has it enabled, and is not sent if none does.

## How to enable or disable telemetry

Go to **Settings → Devices & Services → Hitachi Yutaki → Configure** and select the telemetry step. You can enable or disable telemetry at any time.

## Community discussion

See [Discussion #200](https://github.com/alepee/hass-hitachi_yutaki/discussions/200) for context and community feedback on this feature.
