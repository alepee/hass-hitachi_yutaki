"""Compact the R2 telemetry archive into a local Parquet data lake.

Each UTC day of `metrics/` and `snapshots/` (many small JSON objects, gzipped
or not) becomes one zstd Parquet file per type, Hive-partitioned like the
archive:

    <lake>/metrics/year=YYYY/month=MM/day=DD/part-0.parquet     one row per point
    <lake>/snapshots/year=YYYY/month=MM/day=DD/part-0.parquet   one row per snapshot
    <lake>/installations/date=YYYY-MM-DD/part-0.parquet         daily copy of installations/
    <lake>/_manifest/YYYY-MM-DD.json                            what was compacted, and checked

A day is written only once it is complete (strictly before today, UTC) and is
checked before its manifest is written: every object listed in R2 must appear
in the Parquet file, and the row count must match what was read. A day with a
manifest is skipped, so the job is idempotent and catches up on missed days.

With `--upload`, the Parquet files are also copied to the bucket under `lake/`,
the off-site backup of the lake once the raw JSON expires from R2.

Credentials come from the environment, never from the command line:
R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
import gzip
import json
import logging
import os
from pathlib import Path
import sys
import time

import boto3
from botocore.config import Config
import duckdb

BUCKET = "hitachi-telemetry-archive"
KINDS = ("metrics", "snapshots")
DOWNLOAD_WORKERS = int(os.environ.get("LAKE_DOWNLOAD_WORKERS", "64"))
DOWNLOAD_CHUNK = 1000
# First day of the archive (bucket created 2026-03-15).
ARCHIVE_START = date(2026, 3, 13)

_LOGGER = logging.getLogger("lake")


def connect(
    memory_limit: str, threads: int, temp_dir: Path
) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with bounded resources (local files only)."""
    con = duckdb.connect()
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute(f"SET threads = {threads}")
    con.execute(f"SET temp_directory = '{temp_dir}'")
    con.execute("SET preserve_insertion_order = false")
    return con


def s3_client():
    """S3 client on the R2 endpoint, sized for parallel downloads."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(
            max_pool_connections=DOWNLOAD_WORKERS,
            retries={"max_attempts": 8, "mode": "adaptive"},
        ),
    )


def day_path(day: date) -> str:
    """Hive partition suffix of a day."""
    return f"year={day:%Y}/month={day:%m}/day={day:%d}"


def list_objects(s3, prefix: str) -> list[str]:
    """Keys of the JSON objects under a prefix."""
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=prefix
    ):
        keys += [o["Key"] for o in page.get("Contents", []) if ".json" in o["Key"]]
    return keys


def flatten(kind: str, payload: dict, source: str) -> list[dict]:
    """Turn one archived payload into rows: one per metrics point, one per snapshot."""
    if kind == "metrics":
        ident = {
            "instance_hash": payload.get("instance_hash"),
            "device_hash": payload.get("device_hash"),
            "source": source,
        }
        return [{**ident, **point} for point in payload.get("points", [])]
    row = {k: v for k, v in payload.items() if k not in ("type", "registers")}
    # Register addresses vary per gateway and profile: one JSON column rather
    # than a few hundred sparse ones.
    row["registers"] = json.dumps(payload.get("registers", {}), separators=(",", ":"))
    row["source"] = source
    return [row]


def download_day(s3, kind: str, keys: list[str], ndjson: Path) -> tuple[int, int]:
    """Fetch the objects in parallel, flattened to a local NDJSON file.

    Returns (objects read, rows written). Objects are small and numerous, so
    throughput is bound by request latency: many concurrent requests, one pass.
    """

    def fetch(key: str) -> tuple[str, bytes]:
        return key, s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()

    read = rows = 0
    with ThreadPoolExecutor(DOWNLOAD_WORKERS) as pool, ndjson.open("w") as out:
        # By chunks: `map` holds every finished body until the consumer reaches
        # it, so one call over a whole day would buffer most of it in memory.
        for start in range(0, len(keys), DOWNLOAD_CHUNK):
            for key, content in pool.map(fetch, keys[start : start + DOWNLOAD_CHUNK]):
                raw = gzip.decompress(content) if key.endswith(".gz") else content
                for row in flatten(kind, json.loads(raw), key):
                    out.write(json.dumps(row, separators=(",", ":")) + "\n")
                    rows += 1
                read += 1
    return read, rows


def ndjson_to_parquet(con: duckdb.DuckDBPyConnection, ndjson: Path, out: Path) -> None:
    """Convert a local NDJSON file to zstd Parquet, streaming.

    Inferring the schema over every row is cheap on a local file, and types a
    key that is an int on most units and a float on one consistently.
    """
    for path in (ndjson, out):
        if "'" in str(path):
            raise ValueError(f"unsupported path: {path}")
    con.execute(
        f"COPY (SELECT * FROM read_json_auto('{ndjson}', format = 'newline_delimited', "  # noqa: S608 - checked above
        f"sample_size = -1)) TO '{out}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880)"
    )


def compact_day(
    con: duckdb.DuckDBPyConnection, s3, kind: str, day: date, lake: Path, work: Path
) -> dict[str, int]:
    """Compact one day of one payload type; return what the manifest records."""
    objects = list_objects(s3, f"{kind}/{day_path(day)}/")
    out = lake / kind / day_path(day) / "part-0.parquet"
    if not objects:
        out.unlink(missing_ok=True)
        return {"objects": 0, "rows": 0}

    ndjson = work / f"{kind}-{day}.ndjson"
    try:
        read, rows = download_day(s3, kind, objects, ndjson)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".parquet.tmp")
        ndjson_to_parquet(con, ndjson, tmp)
    finally:
        ndjson.unlink(missing_ok=True)

    # Check against the file actually written: every listed object, every row.
    written_rows, written_sources = con.execute(
        "SELECT count(*), count(DISTINCT source) FROM read_parquet(?)", [str(tmp)]
    ).fetchone()
    expected_sources = len(objects) if kind == "snapshots" else None
    if (
        read != len(objects)
        or written_rows != rows
        or (expected_sources is not None and written_sources != expected_sources)
    ):
        tmp.unlink()
        raise RuntimeError(
            f"{kind} {day}: check failed, {len(objects)} objects listed, {read} read, "
            f"{rows} rows flattened, {written_rows} rows and {written_sources} "
            "sources written"
        )
    tmp.replace(out)
    return {
        "objects": len(objects),
        "rows": rows,
        "sources": written_sources,
        "bytes": out.stat().st_size,
    }


def copy_installations(
    con: duckdb.DuckDBPyConnection, s3, day: date, lake: Path, work: Path
) -> dict[str, int]:
    """Keep a dated copy of the current installation documents."""
    keys = list_objects(s3, "installations/")
    ndjson = work / "installations.ndjson"
    with ndjson.open("w") as out:
        for key in keys:
            payload = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
            out.write(json.dumps({**payload, "source": key}) + "\n")
    out_path = lake / "installations" / f"date={day:%Y-%m-%d}" / "part-0.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        ndjson_to_parquet(con, ndjson, out_path)
    finally:
        ndjson.unlink(missing_ok=True)
    rows = con.execute(
        "SELECT count(*) FROM read_parquet(?)", [str(out_path)]
    ).fetchone()[0]
    if rows != len(keys):
        raise RuntimeError(
            f"installations: {len(keys)} objects but {rows} rows written"
        )
    return {"rows": rows}


def upload(s3, lake: Path, files: list[Path]) -> None:
    """Copy Parquet files to the bucket under lake/, same relative path."""
    for path in files:
        s3.upload_file(str(path), BUCKET, f"lake/{path.relative_to(lake).as_posix()}")


def process_day(
    con: duckdb.DuckDBPyConnection,
    s3,
    day: date,
    lake: Path,
    work: Path,
    do_upload: bool,
) -> None:
    """Compact, check and record one day."""
    started = time.monotonic()
    manifest = {"day": day.isoformat()}
    for kind in KINDS:
        manifest[kind] = compact_day(con, s3, kind, day, lake, work)
    files = [
        lake / kind / day_path(day) / "part-0.parquet"
        for kind in KINDS
        if manifest[kind]["objects"]
    ]
    if day == datetime.now(UTC).date() - timedelta(days=1):
        manifest["installations"] = copy_installations(con, s3, day, lake, work)
        files.append(lake / "installations" / f"date={day:%Y-%m-%d}" / "part-0.parquet")
    if do_upload:
        upload(s3, lake, files)
        manifest["uploaded"] = True
    manifest["seconds"] = round(time.monotonic() - started, 1)
    manifest["compacted_at"] = datetime.now(UTC).isoformat(timespec="seconds")

    path = lake / "_manifest" / f"{day.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    _LOGGER.info("%s", json.dumps(manifest))


def pending_days(lake: Path, start: date, end: date) -> list[date]:
    """Days in [start, end] without a manifest."""
    days = []
    day = start
    while day <= end:
        if not (lake / "_manifest" / f"{day.isoformat()}.json").exists():
            days.append(day)
        day += timedelta(days=1)
    return days


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--lake", type=Path, default=Path(os.environ.get("LAKE_DIR", "lake"))
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        help="first day to process (default: 35 days ago, i.e. R2's retention)",
    )
    parser.add_argument(
        "--end", type=date.fromisoformat, help="last day (default: yesterday, UTC)"
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.environ["LAKE_WORK_DIR"])
        if os.environ.get("LAKE_WORK_DIR")
        else None,
        help="scratch space for one day of NDJSON, ~3 GB; keep it on a local disk (default: <lake>/_tmp)",
    )
    parser.add_argument(
        "--force", action="store_true", help="redo days that have a manifest"
    )
    parser.add_argument(
        "--upload", action="store_true", help="copy Parquet files to R2 lake/"
    )
    parser.add_argument(
        "--memory-limit", default=os.environ.get("LAKE_MEMORY_LIMIT", "1GB")
    )
    parser.add_argument(
        "--threads", type=int, default=int(os.environ.get("LAKE_THREADS", "8"))
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    end = min(args.end or yesterday, yesterday)
    start = max(args.start or yesterday - timedelta(days=34), ARCHIVE_START)
    days = _range(start, end) if args.force else pending_days(args.lake, start, end)
    _LOGGER.info("%d day(s) to process between %s and %s", len(days), start, end)

    work = args.work_dir or args.lake / "_tmp"
    con = connect(args.memory_limit, args.threads, work)
    s3 = s3_client()
    failed = 0
    for day in days:
        try:
            process_day(con, s3, day, args.lake, work, args.upload)
        except Exception:  # noqa: BLE001 - one bad day must not stop the others
            _LOGGER.exception("day %s failed", day)
            failed += 1
    return 1 if failed else 0


def _range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


if __name__ == "__main__":
    sys.exit(main())
