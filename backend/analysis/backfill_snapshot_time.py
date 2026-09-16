#!/usr/bin/env -S uv run --with boto3 --script
"""Backfill the missing ``time`` field of archived register snapshots (#442).

Until the Worker fix for #442, ``validateSnapshot`` rebuilt the snapshot
payload without copying the client's ``time``, so every object under
``snapshots/`` was undated in its body. The only date was the ingestion epoch
in the object name (``snap_<epoch>_<nonce>_<hash>.json``). The snapshot is
sent right after the first successful poll, so that epoch is within seconds of
the client timestamp and an honest substitute.

This script rewrites each undated object in place (same key, same custom
metadata) with::

    "time": "<epoch as ISO-8601 UTC>",
    "time_source": "backfill"

``time_source`` tells a reconstructed timestamp from a client-reported one:
objects written by the fixed Worker carry no ``time_source``.

Idempotent: objects that already carry ``time`` are skipped, so the script can
be re-run after the Worker fix ships without touching new objects. Dry-run by
default; pass ``--apply`` to write.

Order of operations: deploy the Worker fix first (``make worker-deploy``),
then run this, so nothing new lands undated in between.

Usage::

    ./backfill_snapshot_time.py             # count only
    ./backfill_snapshot_time.py --apply     # rewrite

Requires R2 S3 credentials with **write** access to the bucket in
``../.env.r2`` (``R2_KEY_ID`` / ``R2_SECRET``). The read-only token used by
the analysis scripts is not enough. ``boto3`` is pulled in by the ``uv run``
shebang; the rest is stdlib.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import json
import os
import pathlib
import re
import sys

import boto3

ACCOUNT_ID = "04cd76fb78280d03639e8d948d7ae410"
BUCKET = "hitachi-telemetry-archive"
PREFIX = "snapshots/"
KEY_EPOCH = re.compile(r"/snap_(\d+)_")


def load_env(path: pathlib.Path) -> dict[str, str]:
    """Read ``KEY=VALUE`` lines; the environment wins over the file."""
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip("'\"")
    values.update({k: os.environ[k] for k in ("R2_KEY_ID", "R2_SECRET") if k in os.environ})
    return values


def make_client(env: dict[str, str]):
    """Build an S3 client pointed at the R2 endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET"],
        region_name="auto",
    )


def list_keys(s3) -> list[str]:
    """List every object key under the snapshots prefix."""
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def epoch_from_key(key: str) -> int | None:
    """Return the ingestion epoch embedded in the object name."""
    m = KEY_EPOCH.search(key)
    return int(m.group(1)) if m else None


def process(s3, key: str, apply: bool) -> str:
    """Return ``skipped`` / ``would_fix`` / ``fixed`` / ``no_epoch`` / ``unreadable``."""
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    try:
        body = json.loads(obj["Body"].read())
    except (ValueError, UnicodeDecodeError):
        return "unreadable"
    if not isinstance(body, dict):
        return "unreadable"
    if "time" in body:
        return "skipped"
    epoch = epoch_from_key(key)
    if epoch is None:
        return "no_epoch"
    if not apply:
        return "would_fix"
    body["time"] = datetime.fromtimestamp(epoch, tz=UTC).isoformat().replace("+00:00", "Z")
    body["time_source"] = "backfill"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(body).encode(),
        ContentType="application/json",
        Metadata=obj.get("Metadata", {}),
    )
    return "fixed"


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="rewrite objects (default: dry run)")
    parser.add_argument("--workers", type=int, default=16, help="parallel R2 requests")
    args = parser.parse_args()

    here = pathlib.Path(__file__).resolve().parent
    env = load_env(here.parent / ".env.r2")
    if "R2_KEY_ID" not in env or "R2_SECRET" not in env:
        print("R2_KEY_ID / R2_SECRET missing (backend/.env.r2 or environment)", file=sys.stderr)
        return 2

    s3 = make_client(env)
    keys = list_keys(s3)
    print(f"{len(keys)} objects under {PREFIX} ({'APPLY' if args.apply else 'dry run'})")

    counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, s3, key, args.apply): key for key in keys}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                outcome = fut.result()
            except Exception as exc:  # noqa: BLE001 - report and keep going
                outcome = "error"
                print(f"error on {futures[fut]}: {exc}", file=sys.stderr)
            counts[outcome] = counts.get(outcome, 0) + 1
            if i % 500 == 0:
                print(f"  {i}/{len(keys)}", file=sys.stderr)

    for outcome in ("fixed", "would_fix", "skipped", "no_epoch", "unreadable", "error"):
        if counts.get(outcome):
            print(f"{outcome:>10}: {counts[outcome]}")
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
