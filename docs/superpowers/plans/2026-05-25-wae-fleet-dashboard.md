# WAE Fleet Inventory Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Grafana fleet-inventory dashboard fed by Cloudflare Workers Analytics Engine (WAE), showing active installation versions and configuration without running a notebook.

**Architecture:** The Worker gains a second sink used only for the `installation` payload — `env.AE.writeDataPoint(...)`. R2 stays the single permanent archive for all payload types. The integration re-sends the `installation` payload once per UTC day so WAE's 90-day window reflects the truly-active fleet. Grafana Cloud reads the WAE SQL API.

**Tech Stack:** Cloudflare Worker (TypeScript), Workers Analytics Engine, Grafana Cloud (Altinity ClickHouse plugin), Home Assistant integration (Python), pytest.

**Branch:** Work happens on `feat/wae-fleet-dashboard` (already created; the design spec is committed there at `docs/superpowers/specs/2026-05-25-wae-fleet-dashboard-design.md`).

---

## File structure

### Files to modify
- `custom_components/hitachi_yutaki/coordinator.py` — track last-send date, re-arm daily, set date on success
- `backend/worker/src/types.ts` — add `AE: AnalyticsEngineDataset` to `Env`
- `backend/worker/wrangler.toml` — add the `analytics_engine_datasets` binding
- `backend/worker/src/index.ts` — write the installation data point to WAE
- `backend/README.md` — document the WAE dataset + Grafana setup
- `docs/reference/telemetry.md` — note the WAE projection for the installation type
- `CLAUDE.md` — update the telemetry backend bullet
- `CHANGELOG.md` — Unreleased entry

### Files to create
- `tests/test_coordinator_installation_resend.py` — unit test for the daily re-arm
- `backend/grafana/installations-dashboard.json` — exported Grafana dashboard model

### Files left untouched (intentional)
- `custom_components/hitachi_yutaki/telemetry/*` — no payload-contract change
- `backend/worker/src/archive.ts`, `validator.ts`, `rate-limiter.ts` — no change

---

## Tasks

### Task 1: CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add the Unreleased entry**

Add under `## [Unreleased]` → `### Added` (create the `### Added` subsection if absent):

```markdown
### Added
- Telemetry backend: fleet-inventory dashboard. The Worker now mirrors each `installation` payload into Cloudflare Workers Analytics Engine (dataset `hitachi_installations`), feeding a Grafana dashboard that shows active integration/HA versions, heat-pump profiles, gateway types, and configuration flags (cooling, DHW, pool, S80, circuits, power supply) plus per-installation drill-down by anonymous hash. R2 remains the single permanent archive. The integration re-sends the (anonymous) installation payload once per day so the dashboard's 90-day window reflects the active fleet.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(telemetry): changelog entry for WAE fleet dashboard"
```

---

### Task 2: Integration — re-send `installation` payload once per UTC day

**Files:**
- Modify: `custom_components/hitachi_yutaki/coordinator.py`
- Create: `tests/test_coordinator_installation_resend.py`

The re-arm logic is extracted into a small method so it can be unit-tested without driving a full poll cycle.

- [ ] **Step 1: Write the failing test**

Create `tests/test_coordinator_installation_resend.py`:

```python
"""Tests for the daily re-arm of the installation telemetry payload."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hitachi_yutaki.coordinator import HitachiYutakiDataCoordinator
from custom_components.hitachi_yutaki.telemetry import (
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from homeassistant.const import CONF_SCAN_INTERVAL


@pytest.fixture
def coordinator():
    """Create a coordinator with noop telemetry."""
    hass = MagicMock()
    api_client = MagicMock()
    api_client.connected = True
    api_client.read_values = AsyncMock()
    api_client.register_map.base_keys = ["system_state"]
    profile = MagicMock()
    profile.extra_register_keys = []
    entry = MagicMock()
    entry.data = {CONF_SCAN_INTERVAL: 5}
    with patch("custom_components.hitachi_yutaki.coordinator.ir"):
        coord = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)
    coord.telemetry_collector = TelemetryCollector(level=TelemetryLevel.OFF)
    coord.telemetry_client = NoopTelemetryClient()
    coord._telemetry_meta = {
        "instance_hash": "0" * 64,
        "profile": "yutaki_s",
        "gateway_type": "modbus_atw_mbs_02",
        "ha_version": "2026.5.0",
        "integration_version": "2.1.1",
        "power_supply": "single",
    }
    return coord


def test_rearm_on_new_day_resets_flag(coordinator):
    """Crossing a UTC day boundary re-arms the installation send."""
    coordinator._installation_info_sent = True
    coordinator._installation_sent_date = date(2026, 5, 24)

    coordinator._maybe_rearm_installation_resend(date(2026, 5, 25))

    assert coordinator._installation_info_sent is False


def test_no_rearm_same_day(coordinator):
    """Within the same UTC day the flag stays set."""
    coordinator._installation_info_sent = True
    coordinator._installation_sent_date = date(2026, 5, 25)

    coordinator._maybe_rearm_installation_resend(date(2026, 5, 25))

    assert coordinator._installation_info_sent is True


def test_no_rearm_before_first_send(coordinator):
    """Before any send (date is None) the flag is left untouched."""
    coordinator._installation_info_sent = False
    coordinator._installation_sent_date = None

    coordinator._maybe_rearm_installation_resend(date(2026, 5, 25))

    assert coordinator._installation_info_sent is False
    assert coordinator._installation_sent_date is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `make test-domain` is HA-free; this test needs HA, so run:
```bash
python -m pytest tests/test_coordinator_installation_resend.py -v
```
Expected: FAIL — `AttributeError: ... has no attribute '_maybe_rearm_installation_resend'` (and `_installation_sent_date`).

- [ ] **Step 3: Add the `date` import**

In `custom_components/hitachi_yutaki/coordinator.py`, line 6 currently reads:

```python
from datetime import UTC, datetime, timedelta
```

Change it to:

```python
from datetime import UTC, date, datetime, timedelta
```

- [ ] **Step 4: Add the `_installation_sent_date` attribute**

In `__init__`, immediately after the line `self._installation_info_sent: bool = False` (line 77), add:

```python
        self._installation_sent_date: date | None = None
```

- [ ] **Step 5: Add the re-arm method**

Add this method to the coordinator, immediately before `_send_installation_info` (line 214):

```python
    def _maybe_rearm_installation_resend(self, today: date) -> None:
        """Re-arm the installation telemetry send when the UTC day changes.

        WAE retains 90 days, so a stable installation that never restarts HA
        would otherwise drop off the fleet dashboard. Re-arming once per UTC
        day keeps the 90-day window populated. The actual send rides the
        existing one-time send path (lock + exponential backoff).
        """
        if self._installation_sent_date is not None and self._installation_sent_date != today:
            self._installation_info_sent = False
```

- [ ] **Step 6: Call the re-arm in the poll loop**

In `_async_update_data`, the block at lines 157-160 currently reads:

```python
            # Send one-time telemetry data (with backoff on failure)
            # Fire-and-forget to avoid blocking the Modbus poll path
            if not self._installation_info_sent or not self._snapshot_sent:
                self.hass.async_create_task(self._send_onetime_telemetry(data))
```

Replace it with:

```python
            # Re-arm the daily installation re-send before the send gate so a
            # stable install stays visible in WAE's 90-day fleet window.
            self._maybe_rearm_installation_resend(datetime.now(tz=UTC).date())

            # Send one-time telemetry data (with backoff on failure)
            # Fire-and-forget to avoid blocking the Modbus poll path
            if not self._installation_info_sent or not self._snapshot_sent:
                self.hass.async_create_task(self._send_onetime_telemetry(data))
```

- [ ] **Step 7: Record the send date on success**

In `_send_installation_info`, the success branch (lines 244-246) currently reads:

```python
            success = await self.telemetry_client.send_installation(info)
            if success:
                self._installation_info_sent = True
```

Change it to:

```python
            success = await self.telemetry_client.send_installation(info)
            if success:
                self._installation_info_sent = True
                self._installation_sent_date = datetime.now(tz=UTC).date()
```

- [ ] **Step 7b: Reset the backoff delay on a successful one-time send**

The daily re-send now exercises `_send_onetime_telemetry` far more often than the
old once-per-session path. Today its success branch clears `_telemetry_next_retry`
but leaves `_telemetry_retry_delay` permanently inflated after any transient
failure. In `_send_onetime_telemetry`, the success branch (lines 211-212)
currently reads:

```python
            else:
                self._telemetry_next_retry = None
```

Change it to:

```python
            else:
                self._telemetry_next_retry = None
                self._telemetry_retry_delay = 30
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `python -m pytest tests/test_coordinator_installation_resend.py -v`
Expected: 3 passed.

- [ ] **Step 9: Run lint + the full coordinator suite**

```bash
make lint
python -m pytest tests/test_coordinator.py tests/test_coordinator_installation_resend.py -v
```
Expected: lint clean; all tests pass.

- [ ] **Step 10: Commit**

```bash
git add custom_components/hitachi_yutaki/coordinator.py tests/test_coordinator_installation_resend.py
git commit -m "feat(telemetry): re-send installation payload once per UTC day"
```

---

### Task 3: Worker — add the WAE binding

**Files:**
- Modify: `backend/worker/src/types.ts`
- Modify: `backend/worker/wrangler.toml`

- [ ] **Step 1: Add `AE` to the `Env` interface**

In `backend/worker/src/types.ts`, change:

```typescript
export interface Env {
  ARCHIVE: R2Bucket;
}
```

to:

```typescript
export interface Env {
  ARCHIVE: R2Bucket;
  AE: AnalyticsEngineDataset;
}
```

(`AnalyticsEngineDataset` is a global type provided by `@cloudflare/workers-types`, already in `tsconfig.json`.)

- [ ] **Step 2: Add the dataset binding to `wrangler.toml`**

In `backend/worker/wrangler.toml`, after the `[[r2_buckets]]` block and before `[observability]`, add:

```toml
[[analytics_engine_datasets]]
binding = "AE"
dataset = "hitachi_installations"
```

- [ ] **Step 3: Type-check**

```bash
cd backend/worker
npx tsc --noEmit
```
Expected: exit code 0 (the binding is declared but not yet used — that's fine).

- [ ] **Step 4: Dry-run wrangler to confirm the binding parses**

```bash
npx wrangler deploy --dry-run --outdir=/tmp/wae-dry-run
```
Expected: completes successfully and lists both the `ARCHIVE` (R2) and `AE` (Analytics Engine) bindings.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add backend/worker/src/types.ts backend/worker/wrangler.toml
git commit -m "feat(telemetry): add Analytics Engine binding to the worker"
```

---

### Task 4: Worker — write the installation data point to WAE

**Files:**
- Modify: `backend/worker/src/index.ts`

- [ ] **Step 1: Add the WAE write after the R2 archive**

In `backend/worker/src/index.ts`, the block at lines 55-62 currently reads:

```typescript
      try {
        await archiveToR2(env.ARCHIVE, payload);
      } catch (err) {
        console.error("R2 archive failed:", err);
        return new Response("R2 archive unavailable", { status: 502 });
      }

      return new Response(null, { status: 202 });
```

Replace it with:

```typescript
      try {
        await archiveToR2(env.ARCHIVE, payload);
      } catch (err) {
        console.error("R2 archive failed:", err);
        return new Response("R2 archive unavailable", { status: 502 });
      }

      // Mirror installation payloads into Analytics Engine for the fleet
      // dashboard. Non-blocking and best-effort: a WAE failure never changes
      // the response — R2 success is the contract.
      if (payload.type === "installation") {
        try {
          const d = payload.data;
          env.AE.writeDataPoint({
            indexes: [payload.instance_hash],
            blobs: [
              payload.instance_hash,
              d.profile,
              d.gateway_type,
              d.power_supply ?? "",
              d.integration_version ?? "",
              d.ha_version ?? "",
              d.climate_zone ?? "",
            ],
            doubles: [
              d.has_dhw ? 1 : 0,
              d.has_pool ? 1 : 0,
              d.has_cooling ? 1 : 0,
              d.has_secondary_compressor ? 1 : 0,
              d.max_circuits ?? 0,
              d.latitude ?? 0,
              d.longitude ?? 0,
            ],
          });
        } catch (err) {
          console.warn("WAE write failed:", err);
        }
      }

      return new Response(null, { status: 202 });
```

- [ ] **Step 2: Update the file header comment**

In `index.ts`, the header block lists the sinks. Change the line:

```typescript
 *   - Single sink: R2 (permanent JSON archive, partitioned Hive-style)
```

to:

```typescript
 *   - R2 (permanent JSON archive, partitioned Hive-style) — sole archive, all types
 *   - Analytics Engine (dataset hitachi_installations) — installation payloads only, for the fleet dashboard
```

- [ ] **Step 3: Type-check**

```bash
cd backend/worker
npx tsc --noEmit
```
Expected: exit code 0.

- [ ] **Step 4: Commit**

```bash
cd ../..
git add backend/worker/src/index.ts
git commit -m "feat(telemetry): write installation data points to Analytics Engine"
```

---

### Task 5: Worker — local end-to-end verification

**Files:** (none modified — verification only)

- [ ] **Step 1: Start the worker locally**

```bash
cd backend/worker
npx wrangler dev --local
```
Expected: starts on `http://localhost:8787`, lists the `ARCHIVE` and `AE` bindings. Leave running.

- [ ] **Step 2: POST a synthetic installation payload**

In another terminal:

```bash
HASH=$(printf '%064d' 1)
curl -i -X POST http://localhost:8787/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Instance-Hash: $HASH" \
  --data '{"type":"installation","instance_hash":"'"$HASH"'","data":{"profile":"yutaki_s","gateway_type":"modbus_atw_mbs_02","ha_version":"2026.5.0","integration_version":"2.1.1","power_supply":"single","has_dhw":true,"has_pool":false,"has_cooling":true,"max_circuits":2,"has_secondary_compressor":false}}'
```
Expected: `HTTP/1.1 202 Accepted` with empty body. (In `--local`, WAE writes are accepted but not queryable locally; the absence of a 5xx confirms the write path doesn't throw.)

- [ ] **Step 3: Confirm a malformed payload still returns 4xx**

```bash
curl -i -X POST http://localhost:8787/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Instance-Hash: $HASH" \
  --data '{"type":"installation","instance_hash":"'"$HASH"'","data":{}}'
```
Expected: `HTTP/1.1 400` (validator requires `profile` and `gateway_type`).

- [ ] **Step 4: Stop wrangler dev**

`Ctrl+C`. No commit — verification only.

---

### Task 6: Documentation — backend README, telemetry reference, CLAUDE.md

**Files:**
- Modify: `backend/README.md`
- Modify: `docs/reference/telemetry.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add an Analytics Engine row to the backend README Infrastructure table**

In `backend/README.md`, the table lives under the `## Infrastructure` heading and
already has a `Cloudflare Worker` row and an `R2` row. **Append one row** (do not
replace the table — the Worker and R2 rows must stay). After the edit it reads:

```markdown
| Service | Identifier | Purpose |
|---------|------------|---------|
| **Cloudflare Worker** | `hitachi-telemetry.antoine-04c.workers.dev` | Ingestion proxy |
| **R2** | `hitachi-telemetry-archive` | Permanent JSON archive of all payloads |
| **Analytics Engine** | `hitachi_installations` | Installation payloads mirrored for the Grafana fleet dashboard |
```

Also update the `## Architecture` ASCII diagram (backend/README.md:7-12): under the
`→ R2 (...)` line, add a sibling line `→ Analytics Engine (installation only, fleet dashboard)`.

- [ ] **Step 2: Add a "Fleet dashboard" section to the backend README**

After the "Querying the archive" section, add:

````markdown
## Fleet dashboard (Grafana + Analytics Engine)

Each `installation` payload is mirrored into the Workers Analytics Engine dataset
`hitachi_installations` (the worker auto-creates it on first write). Grafana Cloud
reads it through the WAE SQL API. The dashboard model is committed at
`backend/grafana/installations-dashboard.json`.

**Grafana data source** (Altinity ClickHouse plugin):
- URL: `https://api.cloudflare.com/client/v4/accounts/<account_id>/analytics_engine/sql`
- Auth: add a custom header `Authorization: Bearer <token>`, where `<token>` has the
  `Account Analytics Read` permission. Leave the plugin's own auth settings off.

**Base query — latest config per active install:**

```sql
SELECT
  blob1 AS instance_hash,
  argMax(blob2, timestamp) AS profile,
  argMax(blob3, timestamp) AS gateway_type,
  argMax(blob4, timestamp) AS power_supply,
  argMax(blob5, timestamp) AS integration_version,
  argMax(blob6, timestamp) AS ha_version,
  argMax(blob7, timestamp) AS climate_zone,
  argMax(double5, timestamp) AS max_circuits
FROM hitachi_installations
WHERE timestamp > NOW() - INTERVAL '90' DAY
GROUP BY instance_hash
```

"Active" means the install sent telemetry in the last 90 days (the integration
re-sends the installation payload daily, so the window stays populated).

> **Sampling note:** WAE samples high-volume datasets. At the current fleet scale
> (hundreds of installs, ~1 event/install/day) no sampling occurs, so raw `count()`
> is exact. The distribution panels count over a per-hash de-duplicated subquery
> (one row per install), which is sample-safe regardless. If the fleet ever grows
> large enough for WAE to sample, switch raw event counts to `SUM(_sample_interval)`.
````

- [ ] **Step 3: Update `docs/reference/telemetry.md`**

Find the section describing the backend sinks (search for `R2` / `single sink`):

```bash
grep -n "R2\|single sink\|sole sink\|sink" docs/reference/telemetry.md
```

Add a sentence to the backend description: "Installation payloads are additionally mirrored into the Workers Analytics Engine dataset `hitachi_installations`, which powers a Grafana fleet-inventory dashboard. R2 remains the only permanent archive; WAE holds only the anonymous installation dimensions already present in R2 and retains them for 90 days."

- [ ] **Step 4: Update `CLAUDE.md`**

Find the telemetry backend bullet (line ~74):

```markdown
- **Backend**: Cloudflare Worker (ingestion/validation/rate-limit per payload type) → R2 (single sink, permanent JSON archive partitioned Hive-style)
```

Replace with:

```markdown
- **Backend**: Cloudflare Worker (ingestion/validation/rate-limit per payload type) → R2 (permanent JSON archive, partitioned Hive-style, all types). Installation payloads are also mirrored to Workers Analytics Engine (dataset `hitachi_installations`) for a Grafana fleet-inventory dashboard. Integration re-sends installation daily to keep WAE's 90-day window populated.
```

- [ ] **Step 5: Commit**

```bash
git add backend/README.md docs/reference/telemetry.md CLAUDE.md
git commit -m "docs(telemetry): document WAE fleet dashboard"
```

---

### Task 7: Open PR, deploy, verify in production, build Grafana dashboard

**Files:**
- Create: `backend/grafana/installations-dashboard.json` (committed after building it in Grafana — Step 7)

- [ ] **Step 1: Push the branch and open the PR**

```bash
git push -u origin feat/wae-fleet-dashboard
gh pr create --title "feat(telemetry): WAE-backed fleet inventory dashboard" --body "$(cat <<'EOF'
## Summary
- Mirrors each `installation` payload into Workers Analytics Engine (dataset `hitachi_installations`). R2 stays the single permanent archive.
- Re-sends the anonymous installation payload once per UTC day so WAE's 90-day window reflects the active fleet.
- Adds the Grafana dashboard model and documents the WAE + Grafana setup.
- No payload-contract change; fully anonymous (same SHA-256 hash, rounded geoloc).

## Test plan
- [x] `pytest tests/test_coordinator_installation_resend.py`
- [x] `npx tsc --noEmit` in `backend/worker/`
- [x] Local `wrangler dev` — installation POST returns 202, malformed returns 400
- [ ] Post-deploy: WAE SQL query returns rows; Grafana panels render
EOF
)"
```

- [ ] **Step 2: Wait for CI**

```bash
gh pr checks --watch
```
Expected: all checks pass.

- [ ] **Step 3: Squash-merge and sync main**

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
```

- [ ] **Step 4: Deploy the worker**

```bash
cd backend/worker
npx wrangler deploy
```
Expected: a new Version ID, bindings listing `env.ARCHIVE` **and** `env.AE`.

- [ ] **Step 5: Verify WAE receives data (post-deploy)**

Wait a few minutes for real installation payloads (or trigger one from a dev HA instance). Then query the SQL API directly (replace `<account_id>` and `<token>`):

```bash
curl "https://api.cloudflare.com/client/v4/accounts/<account_id>/analytics_engine/sql" \
  --header "Authorization: Bearer <token>" \
  --data "SELECT count(DISTINCT blob1) AS installs FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '1' DAY"
```
Expected: a JSON result with a non-zero `installs` count once at least one installation payload has landed. If the query errors on `argMax` in later panel queries, confirm the WAE SQL function is supported and adjust the panel SQL accordingly (the `count(DISTINCT ...)` form above uses only core functions and should always work).

- [ ] **Step 6: Build the Grafana dashboard**

In Grafana Cloud, add the Altinity ClickHouse data source (Step 2 of the README section), then create one panel per query below. Set the time range to "Last 90 days".

- **Active installs (Stat):**
```sql
SELECT count(DISTINCT blob1) AS active_installs
FROM hitachi_installations
WHERE timestamp > NOW() - INTERVAL '90' DAY
```

- **By profile (Bar/Pie):**
```sql
SELECT profile, count() AS installs FROM (
  SELECT blob1 AS h, argMax(blob2, timestamp) AS profile
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY profile ORDER BY installs DESC
```

- **By gateway type (Bar/Pie):**
```sql
SELECT gateway_type, count() AS installs FROM (
  SELECT blob1 AS h, argMax(blob3, timestamp) AS gateway_type
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY gateway_type ORDER BY installs DESC
```

- **Integration version distribution (Table):**
```sql
SELECT integration_version, count() AS installs FROM (
  SELECT blob1 AS h, argMax(blob5, timestamp) AS integration_version
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY integration_version ORDER BY installs DESC
```

- **HA version distribution (Table):**
```sql
SELECT ha_version, count() AS installs FROM (
  SELECT blob1 AS h, argMax(blob6, timestamp) AS ha_version
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY ha_version ORDER BY installs DESC
```

- **Capability adoption (Stat, one query for all four):**
```sql
SELECT
  countIf(has_cooling = 1) AS with_cooling,
  countIf(has_dhw = 1) AS with_dhw,
  countIf(has_pool = 1) AS with_pool,
  countIf(has_s80 = 1) AS with_s80,
  count() AS total
FROM (
  SELECT blob1 AS h,
    argMax(double3, timestamp) AS has_cooling,
    argMax(double1, timestamp) AS has_dhw,
    argMax(double2, timestamp) AS has_pool,
    argMax(double4, timestamp) AS has_s80
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
)
```

- **Circuits distribution (Bar):**
```sql
SELECT max_circuits, count() AS installs FROM (
  SELECT blob1 AS h, argMax(double5, timestamp) AS max_circuits
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY max_circuits ORDER BY max_circuits
```

- **Power supply (Pie):**
```sql
SELECT power_supply, count() AS installs FROM (
  SELECT blob1 AS h, argMax(blob4, timestamp) AS power_supply
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY power_supply ORDER BY installs DESC
```

- **By climate zone (Bar/Geomap):**
```sql
SELECT climate_zone, count() AS installs FROM (
  SELECT blob1 AS h, argMax(blob7, timestamp) AS climate_zone
  FROM hitachi_installations WHERE timestamp > NOW() - INTERVAL '90' DAY GROUP BY h
) GROUP BY climate_zone ORDER BY installs DESC
```

- **Per-install drill-down (Table, filterable on `instance_hash`):**
```sql
SELECT
  blob1 AS instance_hash,
  argMax(blob2, timestamp) AS profile,
  argMax(blob3, timestamp) AS gateway_type,
  argMax(blob5, timestamp) AS integration_version,
  argMax(blob6, timestamp) AS ha_version,
  argMax(double5, timestamp) AS max_circuits,
  max(timestamp) AS last_seen
FROM hitachi_installations
WHERE timestamp > NOW() - INTERVAL '90' DAY
GROUP BY instance_hash
ORDER BY last_seen DESC
```

- [ ] **Step 7: Export and commit the dashboard model**

In Grafana: Dashboard settings → JSON Model → copy. Save it to `backend/grafana/installations-dashboard.json`. Then:

```bash
git checkout -b chore/grafana-dashboard-export
git add backend/grafana/installations-dashboard.json
git commit -m "docs(grafana): commit fleet inventory dashboard model"
git push -u origin chore/grafana-dashboard-export
gh pr create --title "docs(grafana): fleet inventory dashboard model" --body "Exported Grafana dashboard JSON for the WAE-backed fleet inventory dashboard."
gh pr merge --squash --delete-branch
```

(Committed via a small follow-up PR because the JSON is only available after the dashboard is built against live data.)

---

## Self-review

**1. Spec coverage**
- [x] WAE binding + write for installation only (Tasks 3, 4)
- [x] R2 unchanged as sole permanent archive (Task 4 keeps the archive call, adds WAE after it)
- [x] Daily re-send of installation payload (Task 2)
- [x] Anonymous — no new field, same hash, rounded geoloc (Task 4 uses only existing `payload.data` fields)
- [x] Grafana data source + panels + drill-down + dashboard JSON committed (Tasks 6, 7)
- [x] Docs: README, telemetry.md, CLAUDE.md (Task 6)
- [x] CHANGELOG (Task 1)
- [x] Tests: daily re-arm unit test (Task 2), worker e2e (Task 5)
- [x] Out of scope respected: metrics/daily_stats/snapshot not written to WAE (Task 4 guards on `payload.type === "installation"`)

**2. Placeholder scan**
No "TBD"/"implement later"/vague error handling. Every code step shows the full content. The only deferred artifact is `installations-dashboard.json`, which is intentionally produced by exporting from Grafana after the dashboard is built against live data (Task 7 step 7) — the panel SQL it will contain is fully specified in step 6.

**3. Type / name consistency**
- `_maybe_rearm_installation_resend(today: date)` — same signature in the method (Task 2 step 5), the call site (step 6), and the tests (step 1).
- `_installation_sent_date` — declared (step 4), set (step 7), used (step 5), asserted in tests (step 1).
- `AE: AnalyticsEngineDataset` — declared in `Env` (Task 3) and used as `env.AE.writeDataPoint` (Task 4).
- Dataset name `hitachi_installations` — consistent across `wrangler.toml` (Task 3), README + queries (Task 6/7), and CLAUDE.md (Task 6).
- Blob/double indices in the write (Task 4) match the SQL column references in every panel query (Task 7 step 6): blob2=profile, blob3=gateway_type, blob4=power_supply, blob5=integration_version, blob6=ha_version, blob7=climate_zone; double1=has_dhw, double2=has_pool, double3=has_cooling, double4=has_secondary_compressor, double5=max_circuits.

No drift detected.
