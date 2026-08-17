# Per-gateway telemetry identity (`device_hash`)

**Status:** Design approved, ready for implementation planning.
**Issue:** [#395](https://github.com/alepee/hass-hitachi_yutaki/issues/395)

## Problem

Telemetry identifies a sender by `instance_hash = sha256(HA instance_id)`
(`__init__.py:412-413`). That value is derived from the Home Assistant instance,
not from the config entry, so **every Hitachi config entry on the same HA
instance sends the same identity**.

The reporter of #395 runs four entries (`PAC 1`, `ECS 1`, `ECS 2`, `PAC 2`) on
one HA instance. Each entry arms its own 5-minute flush timer
(`__init__.py:696-705`), all within a few seconds of each other at startup. The
Worker rate-limits to 1 request per 60s per `(instance_hash, payload_type)`
(`rate-limiter.ts`), so all but one flush per cycle is rejected with 429,
forever.

Three distinct defects follow from the shared identity:

1. **Guaranteed telemetry loss on multi-gateway installs.** N-1 of N entries are
   rejected every cycle. `async_flush_telemetry` (`coordinator.py:364-384`)
   clears the buffer *before* sending, so rejected points are dropped, not
   retried.
2. **Silent data corruption in the archive.** `archive.ts:60` writes
   installations to a single key, `installations/install_<hash12>.json`. Four
   entries with different profiles overwrite each other; the archived profile is
   whichever payload landed last. `archive.ts:65-68` builds metrics keys as
   `batch_<ts>_<hash12>.json` with `ts` in **seconds**, so two entries flushing
   in the same second collide and one batch silently overwrites the other.
3. **Undiagnosable failures.** The cause is logged at DEBUG
   (`http_client.py:80`, the 429 branch) while the coordinator logs a
   context-free WARNING (`coordinator.py:381`, `"Telemetry flush: send returned
   failure"`). No log line carries a config-entry identifier, so on a
   multi-gateway install there is no way to tell which entry failed. The
   reporter resorted to `curl`-ing the ingestion endpoint before opening the
   issue.

## Goal

Give each heat-pump unit its own telemetry identity, so that the rate limit, the
R2 archive and the fleet dashboard all address a machine rather than a
household, **without breaking continuity of the existing fleet history**.

## Non-goals

- No change to the 60s rate-limit window, or to the 5-minute flush cadence.
- No change to telemetry consent UX (consent stays per config entry).
- No `0xFFFF` sentinel filtering. A separate issue covers the register-read
  guard; see [Interaction with the `0xFFFF` sentinel bug](#interaction-with-the-0xffff-sentinel-bug).
- No revival of the `daily_stats` payload type. It is still accepted by the
  validator but no longer produced by the integration; it inherits the new key
  layout mechanically and gets no dedicated work.
- No backfill or rewrite of historical R2 objects. `device_hash` was never sent,
  so it cannot be reconstructed after the fact.

## Key decision: additive, not a replacement

`instance_hash` **stays in every payload, unchanged**. `device_hash` is added
alongside it. This is what makes continuity free: every new payload carries both
identifiers, so it *is* the old↔new reconciliation record. No mapping table has
to be built or maintained.

### Identity derivation

```
device_hash = sha256(f"{instance_id}:{entry.unique_id}")
```

`entry.unique_id` is `hitachi_yutaki_<hw_id>_<unit_id>`, built by the config flow
from the gateway hardware identifier read over Modbus, with an IP+slave fallback
(`config_flow.py:363-378`). It is chosen over `entry.entry_id` because it is
tied to the hardware: deleting and re-adding a config entry keeps the same
machine identity in the fleet, preserving its history.

`entry.unique_id` is non-`None` at the point telemetry is wired: the back-fill at
`__init__.py:310-358` runs before the telemetry setup at `__init__.py:400-432`.
No degraded path is needed, but the invariant is asserted at the derivation site
rather than assumed: `hash_device_id` is typed `(str, str)`, and a `None` slipping
through would hash the literal `"None"` and silently give every entry the same
identity again, which is the very bug being fixed. Setup fails loudly instead.

Salting with `instance_id` keeps `device_hash` non-correlatable across HA
instances: two users behind the same gateway model cannot be linked, and the
hardware identifier is never recoverable from the hash. Privacy posture is
unchanged.

#### Related fix: `unit_id` missing from the back-fill

The back-fill produces `f"{DOMAIN}_{hw_id}"` (`__init__.py:337`) while the
config flow produces `f"{DOMAIN}_{hw_id}_{unit_id}"` (`config_flow.py:365`). On a
multi-unit HC-A(16/64)MB gateway the back-filled form does not distinguish
units. Align the back-fill with the config flow.

This is a live bug, not just a consistency fix. Home Assistant does **not**
enforce `unique_id` uniqueness: `async_update_entry`
(`homeassistant/config_entries.py`) only logs an error when the new value is
already in use and then applies it anyway. The duplicate check was deprecated in
2024.11 and is *intended* to fail in 2025.11, but it does not fail on the pinned
version. So on a multi-unit HC-A(16/64)MB install whose entries still have
`unique_id is None`, if the Modbus hardware-id read fails at back-fill time every
entry back-fills to the same `f"{host}_{device_id}"` and therefore derives the
same `device_hash`, which is exactly the collision #395 is about. It is sticky:
the back-fill only runs while `unique_id` is `None`, so it never re-heals.

The fallback therefore appends the unit id too, matching the config flow:
`f"{host}_{device_id}_{unit_id}"`. Entries that back-filled under a previous
version keep their existing `unique_id` and are unaffected; only entries that
have never been back-filled get the corrected form.

## Continuity per surface

### Workers Analytics Engine: full continuity

WAE holds all of the fleet history and feeds the Grafana Cloud dashboard. Keep
`indexes: [instance_hash]` and **append** `device_hash` as `blobs[7]` (`blob8`),
after `climate_zone`.

WAE blobs are positional. Appending at the end does not shift `blob1`–`blob7`, so
existing dashboard queries keep working untouched. This matters because the
dashboard is not versioned in this repository (`backend/grafana/` holds only
`koppen-zones.geojson`), so any schema change would have to be reapplied by hand
in Grafana Cloud.

The change also makes two previously unanswerable questions answerable:
`count(distinct index1)` is the number of households, `count(distinct blob8)` is
the number of heat pumps. Today neither is correct on multi-gateway installs.

One caveat while the fleet upgrades: a legacy sender has its *instance* hash
written into `blob8`, so `count(distinct blob8)` under-counts multi-gateway
legacy households (all of their units collapse into one value) until they are on
a version that sends `device_hash`. It self-heals, but a dashboard reading taken
during the migration window should not be trusted as a heat-pump count.

### R2 `installations/`: no history to break

`installations/install_<hash12>.json` is a single key overwritten on every send:
current state, not a time series. There is nothing historical to preserve.

New key: `installations/install_<instance12>_<device12>.json`.

The only real risk is the legacy object going stale after a client upgrades:
it would never be written again and would double-count in a `installations/`
scan. So: when the Worker receives an installation payload that carried an
**explicit** `device_hash`, it best-effort deletes
`installations/install_<instance12>.json`. Idempotent, self-healing as the fleet
upgrades, and lossless (the legacy object's content is a subset of the new one).
A delete failure must not fail the request: R2 write success remains the
contract, exactly as with `markRateLimit` and the WAE mirror.

### R2 `metrics/` and `snapshots/`: append-only, nothing breaks

These are timestamped and never overwritten. Old objects stay valid; new objects
gain a filename component. Any DuckDB query that reads object *content*
reconciles by itself, since `instance_hash` has always been in the JSON body and
`device_hash` now joins it.

```
metrics/year=YYYY/month=MM/day=DD/batch_<ts>_<instance12>_<device12>.json
snapshots/year=YYYY/month=MM/day=DD/snap_<ts>_<instance12>_<device12>.json
```

One documented workflow depends on the *filename* hash prefix:
`docs/development/telemetry-dataset.md:42` matches snapshot files against
12-char instance prefixes. It must be updated, and it gets more precise, since
a single unit can now be targeted instead of a whole household.

### Legacy clients: byte-identical behaviour

The Worker treats a payload without `device_hash` as legacy and keeps **today's
exact key layout**, rate-limit keying and WAE write. It does not synthesise
`device_hash = instance_hash` into the key, which would strand the legacy object
and create a redundant new one for no benefit.

Residual, accepted: a legacy multi-entry install can still collide on a metrics
key. Since #324 the rate-limit marker is committed *after* archiving, so two
near-simultaneous requests can both pass the check and both write in the same
second. This is the pre-existing behaviour, it is bounded to un-upgraded
multi-gateway installs, and it disappears on upgrade. Not worth a separate fix.

## Components

### 1. Integration: identity plumbing

- `__init__.py`: derive `device_hash` from `instance_id` and `entry.unique_id`,
  add it to `coordinator._telemetry_meta`, pass it to `HttpTelemetryClient`.
- `telemetry/models.py`: add `device_hash: str` to `InstallationInfo`,
  `MetricsBatch` and `RegisterSnapshot`; emit it from `to_dict()` next to
  `instance_hash`.
- `__init__.py:337`: include `unit_id` in the back-filled `unique_id`.

### 2. Integration: diagnosable failures

- `HttpTelemetryClient` takes a `label` (the config entry title) and prefixes
  every log line with it, so a multi-gateway install can tell its entries apart.
- The 429 branch (`http_client.py:80`) logs at WARNING like every other 4xx.
  Once identities are per-unit, a 429 means something is genuinely wrong and
  must be visible. Drop the DEBUG special case.
- `coordinator.py:381` includes the entry label in the flush-failure warning.

No "you have multiple gateways" hint: with per-unit identities that cause is
gone, and the remaining value is generic diagnosability for any 4xx (400
validation, 413 payload too large).

### 3. Integration: stop dropping points on failure

`async_flush_telemetry` clears the buffer before sending, so a failed send loses
its points. Add `TelemetryCollector.requeue(points)`.

Two bounds, both required:

- **Age.** Drop re-queued points older than `MAX_POINT_AGE = 30 minutes`, which
  matches the buffer's natural window (360 points at a 5s poll interval). A
  metrics batch that is half an hour stale has no analytical value.
- **Size.** After merging, keep the **newest** `maxlen` points. `deque.appendleft`
  and `extendleft` on a bounded deque evict from the *right*, i.e. the newest
  points, the opposite of what is wanted. So rebuild explicitly:

  ```python
  merged = kept_requeued + list(self._buffer)
  self._buffer = deque(merged[-self._buffer.maxlen:], maxlen=self._buffer.maxlen)
  ```

Re-queueing on its own turns a transient outage into a permanent one, so two
further guards are part of the same component:

- **Bound the batch, not just the buffer.** `flush()` returns at most
  `MAX_FLUSH_POINTS = 80` points, oldest first, and leaves the rest buffered.
  Without it a failed cycle adds its ~60 points back and the next batch grows
  until the buffer cap; a 240-point batch of real field data serializes to about
  263 KB, over the endpoint's 256 KB limit, and every send from then on is
  rejected with 413. The cap is a client-side bound: the client cannot see the
  server limit, so it must simply never approach it. At the cap a batch built
  from the real Yutampo R32 snapshot is 88 KB.
- **Never re-queue a batch the server refused as too large.** `send_*` returns a
  `SendResult` (`SUCCESS` / `FAILED` / `PAYLOAD_TOO_LARGE`) instead of a bool,
  and the coordinator re-queues only on `FAILED`. A 413 drops its points with a
  WARNING naming the entry. `SendResult.__bool__` follows `SUCCESS`, so callers
  that only care whether the payload landed are unchanged.

### 4. Worker: validation

- `validator.ts`: accept an optional `device_hash`, validated against the same
  `/^[a-f0-9]{64}$/` regex as `instance_hash`. Carry a flag on the validated
  payload recording whether it was explicitly present, since that flag selects
  the key layout.
- Reject a malformed `device_hash` with 400 rather than silently falling back to
  legacy: a client that sends the field must send it correctly.

### 5. Worker: rate limiting

`rate-limiter.ts` keys on `(device_hash, payload_type)`, where `device_hash`
falls back to `instance_hash` for legacy payloads. Legacy senders keep exactly
today's limit; upgraded senders get one slot per unit. The check-then-mark
contract from #324 is untouched.

### 6. Worker: archive

`archive.ts` selects the key layout on the explicit-`device_hash` flag, per the
layouts above, and adds `device_hash` to `customMetadata`. Installation payloads
with an explicit `device_hash` additionally sweep the legacy key, best-effort.

### 7. Worker: WAE

Append `device_hash` as `blobs[7]`. For legacy payloads write `instance_hash`
there, so the column is never empty and `count(distinct blob8)` is correct
across both generations.

## Testing

Domain and unit level, no new HA mocks:

- **Identity**: derivation is stable for a given `(instance_id, unique_id)`, and
  differs across entries of the same instance.
- **Models**: `to_dict()` emits both hashes for all three payload types.
- **Collector**: `requeue` drops points past `MAX_POINT_AGE`; keeps the newest
  on overflow (the regression guard against the `extendleft` eviction trap);
  a re-queue followed by a successful flush sends the re-queued points once.
- **Coordinator**: a failed send re-queues instead of dropping; the warning
  carries the entry label.
- **Worker validator**: legacy payload accepted, explicit `device_hash`
  accepted, malformed `device_hash` rejected with 400.
- **Worker rate limiter**: two entries of one instance no longer contend; a
  legacy payload still contends with itself.
- **Worker archive**: both key layouts; legacy sweep fires only on explicit
  `device_hash`; a sweep failure does not fail the request.

## Interaction with the `0xFFFF` sentinel bug

A parallel investigation found that when an HC-A gateway loses its unit, every
register without a deserializer returns a raw `65535`, and the integration
publishes a superficially coherent state (`is_compressor_running` and
`is_defrosting` both true, `electrical_power` in the thousands of kW).
`TelemetryCollector.collect` only filters on `is_available`
(`collector.py:53-55`), so those points are archived as valid.

That is a separate issue, fixed at the register-read layer. It matters here for
one reason: **re-queueing must not extend the lifetime of such points**. The
30-minute age bound in Component 3 is what guarantees it: a broken install
cannot fill its buffer with garbage that evicts later valid points.

## Documentation to update

Per the code-area → doc-file map in `AGENT.md`:

- `docs/reference/telemetry.md`: payload contract, identity model, rate limit.
- `docs/development/telemetry-dataset.md`: R2 key layouts, and the
  filename-prefix workflow at line 42.
- `AGENT.md`: the telemetry section's description of the payload identity.
- `CHANGELOG.md`: entry under `[Unreleased]`, referencing #395.

## Deployment

Client and Worker are independently deployable, in either order. The Worker is
backward compatible by design, and an *old* Worker tolerates the new client:
each `validate*` function builds a fresh result object from known fields
(`validator.ts:129-237`) and never rejects unknown top-level keys, so a
`device_hash` sent to an un-upgraded Worker is silently dropped rather than
rejected with a 400.

Deploy the Worker first regardless, so the first upgraded client already
benefits:

```bash
cd backend/worker && npx wrangler deploy
```
