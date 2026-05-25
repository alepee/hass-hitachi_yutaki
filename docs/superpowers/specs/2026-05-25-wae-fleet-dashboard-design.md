# Fleet inventory dashboard via Workers Analytics Engine + Grafana

**Status:** Design approved — ready for implementation planning.

## Goal

Provide a quick, always-on overview of the active fleet of Hitachi Yutaki
installations (active integration/HA versions, heat-pump profiles, gateway
types, and configuration flags) without having to spin up a Jupyter notebook
against the R2 archive. The overview supports both aggregate views and
per-installation drill-down.

## Non-goals

- No change to the telemetry payload contract beyond send cadence (see below).
- No operational-health panels (last-seen alerting, COP quality, send failures).
- No permanent relational state store (D1 was considered and rejected in favor
  of WAE for a 100%-managed analytics path with native Grafana support).
- No ingestion into WAE of `metrics`, `daily_stats`, or `snapshot` payloads.

## Architecture

The Worker gains a **second sink, used only for the `installation` payload**:
Cloudflare Workers Analytics Engine (WAE). R2 remains the single permanent
archive for **all** payload types. WAE is a derived projection that feeds a
Grafana Cloud dashboard.

```
HA integration (installation payload, now re-sent daily)
   → Worker
        ├─ R2 archive (all payload types, permanent)      [unchanged]
        └─ WAE writeDataPoint (installation only)         [new]
                 ↑
        Grafana Cloud reads the WAE SQL API
```

### Why WAE (not D1)

- WAE is the Cloudflare-native analytics product with a first-party SQL API and
  documented Grafana integration. The user already has a Grafana Cloud account.
- WAE writes are non-blocking and schemaless (blobs/doubles), so there are no
  migrations to manage — this avoids repeating the TigerData failure mode
  (schema drift + storage quota) that motivated the R2-only migration.
- The 90-day retention window defines "active fleet" naturally, **provided the
  installation payload is re-sent periodically** (see Component 1).

### Privacy

Fully anonymous, unchanged from today: `instance_hash` is the existing SHA-256
hash, latitude/longitude are already rounded by the anonymizer, and **no new
field is introduced**. WAE only ever holds data already present in R2.

## Components

### 1. Integration (Python) — daily re-send of installation payload

Today `installation` is sent **once** per HA session (the
`_installation_info_sent` flag is set after the first successful poll and only
reset on integration reload / HA restart). Because WAE retains only 90 days, an
installation that has not restarted HA within 90 days would disappear from the
dashboard even though it is still active.

**Change:** track the UTC date of the last installation send; when the current
UTC date differs, reset `_installation_info_sent = False` so the existing
one-time send path re-fires exactly once per day. This rides the existing
`_send_onetime_telemetry` lock + exponential-backoff machinery — a missed day
self-heals on the next poll.

- File: `custom_components/hitachi_yutaki/coordinator.py`
- Scope: ~5 lines (a new `_installation_sent_date` attribute + a date check in
  the poll loop before the existing one-time send gate).
- No payload-contract change: the JSON shape is identical.

### 2. Worker — WAE binding + write

- `backend/worker/wrangler.toml`: add
  ```toml
  [[analytics_engine_datasets]]
  binding = "AE"
  dataset = "hitachi_installations"
  ```
- `backend/worker/src/types.ts`: add `AE: AnalyticsEngineDataset` to `Env`.
- `backend/worker/src/index.ts`: after the R2 archive succeeds, if
  `payload.type === "installation"`, call `env.AE.writeDataPoint(...)`. The call
  is wrapped so a WAE failure is logged at `warn` and never affects the `202`
  response (R2 success remains the contract). WAE writes are non-blocking by
  design.

**Field mapping** (`installation.data` → WAE data point):

| WAE field | Source |
|-----------|--------|
| `index1`  | `instance_hash` (sampling key — groups an install's events) |
| `blob1`   | `instance_hash` |
| `blob2`   | `profile` |
| `blob3`   | `gateway_type` |
| `blob4`   | `power_supply` |
| `blob5`   | `integration_version` |
| `blob6`   | `ha_version` |
| `blob7`   | `climate_zone` (may be empty string) |
| `double1` | `has_dhw` (0/1) |
| `double2` | `has_pool` (0/1) |
| `double3` | `has_cooling` (0/1) |
| `double4` | `has_secondary_compressor` (0/1) — the S80 secondary compressor |
| `double5` | `max_circuits` |
| `double6` | `latitude` (0 if absent) |
| `double7` | `longitude` (0 if absent) |

This is well within WAE per-data-point limits (≤ 20 blobs, ≤ 20 doubles, 1 index).
The dataset is auto-created on first write — no manual setup.

### 3. Grafana Cloud

- **Data source:** Altinity ClickHouse plugin pointed at the WAE SQL API
  (`https://api.cloudflare.com/client/v4/accounts/<account_id>/analytics_engine/sql`),
  auth via a Bearer token with the `Account Analytics Read` permission. (No
  TimescaleDB, no self-hosted provisioning — this is the "replacement story"
  the backend README's removed Grafana section referred to.)
- **Base query — latest config per active install:** use `argMax(blobN, timestamp)`
  grouped by `blob1` (instance_hash), filtered `WHERE timestamp > NOW() - INTERVAL '90' DAY`.
- **Panels:**
  - Stat: count of distinct active installs.
  - Bar/pie: installs by `profile`.
  - Bar/pie: installs by `gateway_type`.
  - Table: `integration_version` distribution.
  - Table: `ha_version` distribution.
  - Stats: % with cooling / DHW / pool / S80 secondary compressor.
  - Bar: `max_circuits` distribution.
  - Pie: `power_supply` (single vs three-phase).
  - Geomap: by `climate_zone` (or rounded lat/lon).
  - Table: per-hash drill-down (latest config per `instance_hash`, filterable) —
    serves issue investigation against a specific anonymous install.
- **Dashboard model:** the Grafana dashboard JSON export is committed to
  `backend/grafana/installations-dashboard.json`. This recreates the
  `backend/grafana/` directory, but as a **single dashboard JSON only** — no
  datasource provisioning files, no TimescaleDB dependency.

## Error handling

- WAE write wrapped in `try/catch`, logged at `warn`; the request still returns
  `202`. R2 success/failure remains the sole determinant of the HTTP status.
- Daily re-send rides the existing one-time backoff + `asyncio.Lock`; a day
  skipped due to a transient failure is retried on the next successful poll.

## Testing

- **Worker:** extend the `wrangler dev` e2e check — POST an `installation`
  payload, assert `202`. (WAE has no local query surface in dev, so the write is
  verified post-deploy via a WAE SQL API query.)
- **Integration:** unit test that crossing a UTC day boundary resets the
  installation-resend flag, and that it stays armed within the same day.
- **Manual, post-deploy:** run a WAE SQL query confirming rows land for the
  expected dataset; then build/import the Grafana panels.

## Files touched (anticipated)

- Modify: `custom_components/hitachi_yutaki/coordinator.py`
- Modify: `backend/worker/wrangler.toml`
- Modify: `backend/worker/src/types.ts`
- Modify: `backend/worker/src/index.ts`
- Add: `backend/grafana/installations-dashboard.json`
- Modify: `backend/README.md` (document the WAE dataset + Grafana setup)
- Modify: `docs/reference/telemetry.md` (note the WAE projection for the installation type)
- Modify: `CLAUDE.md` (update the telemetry backend bullet)
- Modify: `CHANGELOG.md` (Unreleased entry)
- Add: integration unit test for the daily-resend flag
