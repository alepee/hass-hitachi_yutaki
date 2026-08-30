# Building a test dataset from telemetry

The opt-in telemetry archive (Cloudflare R2, bucket `hitachi-telemetry-archive`) holds real, anonymized register snapshots and metrics from the fleet across every heat-pump model. This is the best source of **realistic test fixtures / mock data** for implementations you cannot exercise on your own hardware (e.g. a model or gateway you do not own).

This guide is for agents and maintainers building such a dataset. See [../reference/telemetry.md](../reference/telemetry.md) for how telemetry is produced and [../../backend/README.md](../../backend/README.md) for the backend.

> **Secrets**: never hardcode credentials in the repo or in a committed file. Credentials come from the environment (see below). Rotate any token that was shared in plaintext (chat, ticket).
>
> **Privacy**: the archive is already anonymized (hashed instance id, coarsened temperatures/geolocation). Do **not** republish fleet-wide aggregate counts (number of instances, per-model totals) in public artifacts (issues, PRs, release notes). Commit only the minimal, single-instance data a test needs.

## R2 archive layout

Payloads are stored as individual JSON files, Hive-partitioned by date (`backend/worker/src/archive.ts`):

```
installations/install_<instance12>_<device12>.json   (clients >= this release)
installations/install_<instance12>.json              (legacy, swept on first new send)
snapshots/year=YYYY/month=MM/day=DD/snap_<ts>_<hash12>.json
metrics/year=YYYY/month=MM/day=DD/batch_<ts>_<hash12>.json
daily_stats/year=YYYY/month=MM/daily_<date>_<hash12>.json
```

- `<hash12>` = first 12 chars of the SHA-256 instance hash (legacy layout), or `<instance12>_<device12>` (first 12 chars of the instance hash, then of the device hash) once a client sends `device_hash`.
- **installations** carry `data.profile` (e.g. `yutampo_r32`, `yutaki_s`, `yutaki_s80`), `gateway_type`, `has_dhw/pool/cooling`, `max_circuits`.
- **snapshots** carry a one-time `registers` dict (numeric register values incl. `system_config`): the raw material for fixtures.

## Access path A: Cloudflare REST API (only a Cloudflare API token)

Works with a Cloudflare API token (`cfut_…`) and the account id; no S3 access keys needed. Set them in the environment:

```bash
export CF_TOKEN=…          # Cloudflare API token with R2 read on the bucket
export CF_ACCOUNT=…        # Cloudflare account id
```

- **List** objects (paginate on `result_info.cursor` while `is_truncated`):
  `GET https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT/r2/buckets/hitachi-telemetry-archive/objects?prefix=installations/&per_page=1000`
- **Get** an object body: `GET …/objects/<key>` (returns the raw JSON payload).
- Header: `Authorization: Bearer $CF_TOKEN`.

Workflow to find fixtures for a given model:
1. Page `installations/`, download each, keep those whose `data.profile` matches the target model → collect their instance and device hashes (the object body carries both, and so does its `customMetadata`).
2. Page `snapshots/`, match files whose filename **contains** one of the 12-char hashes. Use a substring match, not an ends-with one: a snapshot from an upgraded client is named `snap_<ts>_<instance12>_<device12>.json`, so its name ends with the *device* hash and an ends-with match on the instance hash finds nothing.
3. Download a matching snapshot for the full `registers` dict (incl. `system_config`).

Object names come in two shapes. Objects written before #395, and those from a client that has not upgraded yet, carry a bare `<instance12>`. Newer ones carry `<instance12>_<device12>`. A substring match on `<instance12>` therefore finds every unit of a household in both shapes, while a substring match on `<instance12>_<device12>` narrows it to one specific heat-pump unit. The same applies to `metrics/` batch filenames.

Note that the archived body of a payload from a client that has not upgraded carries a `device_hash` equal to its `instance_hash`, since the Worker falls back to the instance identity when the field is absent. Counting distinct `device_hash` values over the archive therefore under-counts the units of a household that has not upgraded, exactly as `count(distinct blob8)` does on the Analytics Engine side.

## Access path B: DuckDB + httpfs (R2 S3 credentials)

When R2 S3 access keys are available, query the archive directly with DuckDB (documented in `backend/README.md`):

```sql
INSTALL httpfs; LOAD httpfs;
SET s3_region = 'auto';
SET s3_endpoint = '<account-id>.r2.cloudflarestorage.com';
SET s3_access_key_id = '<r2-access-key>';
SET s3_secret_access_key = '<r2-secret>';

SELECT registers
FROM read_json_auto('s3://hitachi-telemetry-archive/snapshots/year=2026/month=*/day=*/snap_*.json')
WHERE profile = 'yutampo_r32'
LIMIT 1;
```

Performance: globbing thousands of JSON files over `httpfs` is HTTP-HEAD-bound (~10 files/s/thread). Acceptable for a single-day fleet scan or a single-instance multi-day scan; narrow the partition glob.

For fleet-wide analyses (rather than single fixtures), reusable DuckDB-based scripts live in [backend/analysis/](../../backend/analysis/README.md): per-day metric extraction, per-model refrigerant profiles, and a detector replay for false-positive estimation. Credentials go in the gitignored `backend/.env.r2` (`R2_KEY_ID=` / `R2_SECRET=`).

## Turning a snapshot into a fixture

Trim a real snapshot to the fields a test needs, then feed those register values into a test. Tests in this repo build register data inline as Python dicts (see `tests/` for examples, e.g. the `system_config`-driven capability tests in `tests/test_coordinator_capability_flags.py`) rather than loading JSON fixtures, so a real snapshot is best used as the source of the numbers you hard-code, with a provenance comment noting it is real field data. A DHW-only Yutampo R32, for instance, reports `system_config = 16` with phantom water/compressor registers reading a constant `0` rather than a sentinel.

Guidelines:
- Keep the instance anonymous: omit the instance hash and exact timestamps.
- Keep only the registers the test asserts on (plus `system_config` and the `has_*` flags a builder needs).
- Document the origin in a `_comment` key so future readers know it is real field data, not invented.
- Prefer fixtures over mocks when the behavior depends on realistic register combinations (e.g. sensors that read `0` rather than a sentinel on a given model).
