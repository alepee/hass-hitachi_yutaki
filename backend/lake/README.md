# Telemetry data lake

The R2 archive stores each telemetry payload as one small JSON object: about
22,000 objects a day. That is cheap to write but costly to keep, and slow to
query (a fleet-wide scan is bound by per-object HTTP requests). `lake.py`
compacts each UTC day into one zstd Parquet file per payload type, so the
archive can be queried locally with DuckDB and the raw JSON can be given a
short retention in R2.

One day of metrics, about 2.5 GB of JSON, compacts to about 11 MB of Parquet.

## Layout

```
<lake>/metrics/year=YYYY/month=MM/day=DD/part-0.parquet     one row per metrics point
<lake>/snapshots/year=YYYY/month=MM/day=DD/part-0.parquet   one row per register snapshot
<lake>/installations/date=YYYY-MM-DD/part-0.parquet         copy of installations/ on each run day
<lake>/_manifest/YYYY-MM-DD.json                            counts and checks for the day
```

- **metrics**: the payload's `instance_hash` and `device_hash`, the `source`
  object key, then one column per metric key (`time` is a timestamp with time
  zone). A day is the date of a batch's first point, as in the archive, so a
  day can hold a few minutes past midnight.
- **snapshots**: the payload's fields, with `registers` as a JSON column
  (register addresses vary per gateway and profile).
- Columns differ between days as the integration adds metrics: read with
  `union_by_name = true`.

## How a day is processed

1. List the day's objects, download them in parallel (64 connections by
   default) and flatten them to a local NDJSON file.
2. Convert it to Parquet with DuckDB, streaming, in the work dir: DuckDB
   cannot lock a file on an SMB share, and the lake only receives checked files.
3. Check the Parquet file written: every listed object was read, every
   flattened row is there and, for snapshots, every object appears as a
   `source`. Only then is the file copied into the lake and the manifest
   written.

A day is compacted two days later (UTC). The Worker files a batch under its
first point's date only while that date is yesterday, today or tomorrow, and
under the ingestion date otherwise, so a day stops receiving objects once the
next one ends, whatever a client's clock says. A day with a manifest is
skipped, so a run catches up on any day missed since the last one; `--force`
redoes them. A failed day is logged and retried on the next run, and the exit
code is non-zero.

With `--upload`, the day's Parquet files are copied to the bucket under
`lake/`: the off-site copy of the lake, and the permanent archive, since raw
metrics and snapshots expire from R2 after 30 days (bucket lifecycle rule).
Since a day is compacted two days later, the job has about four weeks to catch
up after an outage before a day is lost.

In production it runs as a daily CronJob on the maintainer's cluster, writing
to a NAS share. The job pins this script by commit SHA: a change to `lake.py`
only takes effect once that pin is bumped.

## Running it

Credentials come from the environment: an R2 API token with Object Read &
Write on the bucket.

```bash
export R2_ACCOUNT_ID=… R2_ACCESS_KEY_ID=… R2_SECRET_ACCESS_KEY=…
uv run --no-project --with-requirements backend/lake/requirements.txt \
  python backend/lake/lake.py --lake /path/to/lake --upload
```

| Option | Default | |
|---|---|---|
| `--lake` | `$LAKE_DIR` or `./lake` | lake root |
| `--start`, `--end` | 27 days before `--end`, two days ago | days to consider |
| `--work-dir` | `$LAKE_WORK_DIR` or `<lake>/_tmp` | scratch for one day of NDJSON and Parquet (~3 GB), on a local disk |
| `--memory-limit` | `$LAKE_MEMORY_LIMIT` or `1GB` | DuckDB memory limit |
| `--threads` | `$LAKE_THREADS` or `8` | DuckDB threads |
| | `$LAKE_DOWNLOAD_WORKERS` or `64` | concurrent downloads |
| `--upload` | off | copy the Parquet files to R2 `lake/` |

Measured on a laptop: about 100 s per day and a 1.7 GB peak in memory.

## Querying

```sql
SELECT device_hash, count(*) AS points, avg(outdoor_temp)
FROM read_parquet('/path/to/lake/metrics/**/*.parquet',
                  hive_partitioning = true, union_by_name = true)
WHERE year = 2026 AND month = 11
GROUP BY 1;
```

> **Privacy**: the lake holds the same anonymized data as the archive. Keep it
> out of the repo, and do not republish fleet-wide aggregate counts in public
> artifacts (see [telemetry-dataset.md](../../docs/development/telemetry-dataset.md)).
