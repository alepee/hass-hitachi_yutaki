#!/bin/bash
# Download all installation payloads from the R2 telemetry archive into
# data/installations.json ({hash12: installation_data}), used by analyze.py
# to map instances to heat-pump profiles.
#
# Requires: duckdb, python3, R2 S3 credentials in ../.env.r2 (see README.md).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/data"
source "$HERE/../.env.r2"

duckdb -c "
INSTALL httpfs; LOAD httpfs;
CREATE SECRET r2 (
  TYPE s3,
  KEY_ID '$R2_KEY_ID',
  SECRET '$R2_SECRET',
  REGION 'auto',
  ENDPOINT '04cd76fb78280d03639e8d948d7ae410.r2.cloudflarestorage.com'
);
COPY (
  SELECT instance_hash[1:12] AS hash, data
  FROM read_json(
    's3://hitachi-telemetry-archive/installations/install_*.json',
    columns = {instance_hash: 'VARCHAR', data: 'JSON'}
  )
) TO '$HERE/data/installations_raw.json' (FORMAT json, ARRAY true);
"

python3 - "$HERE" <<'EOF'
import json, pathlib, sys

here = pathlib.Path(sys.argv[1])
raw = json.loads((here / "data" / "installations_raw.json").read_text())
out = {r["hash"]: (json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]) for r in raw}
(here / "data" / "installations.json").write_text(json.dumps(out, indent=1))
(here / "data" / "installations_raw.json").unlink()
print(f"{len(out)} installations")
EOF
