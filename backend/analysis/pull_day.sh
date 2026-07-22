#!/bin/bash
# Pull one day of compressor-running metric points from the R2 telemetry
# archive into data/days/<day>.csv, via DuckDB + httpfs (~1-2 min per fleet-day).
#
# Keeps only points where the compressor runs and the defrost guard is off;
# columns: hash, time, tg, te, evo, outdoor, freq, op_state.
#
# Requires: duckdb, R2 S3 credentials in ../.env.r2 (see README.md).
# Usage: pull_day.sh YYYY-MM-DD [YYYY-MM-DD ...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/data/days"
source "$HERE/../.env.r2"

for DAY in "$@"; do
  Y="${DAY:0:4}"; M="${DAY:5:2}"; D="${DAY:8:2}"
  OUT="$HERE/data/days/$DAY.csv"
  if [ -f "$OUT" ]; then echo "$DAY: already done"; continue; fi

  duckdb -c "
INSTALL httpfs; LOAD httpfs;
CREATE SECRET r2 (
  TYPE s3,
  KEY_ID '$R2_KEY_ID',
  SECRET '$R2_SECRET',
  REGION 'auto',
  ENDPOINT '04cd76fb78280d03639e8d948d7ae410.r2.cloudflarestorage.com'
);
SET threads = 32;
COPY (
  SELECT
    instance_hash[1:12]                                                          AS hash,
    json_extract_string(p.value, '$.time')                                       AS time,
    TRY_CAST(json_extract(p.value, '$.compressor_tg_gas_temp') AS DOUBLE)        AS tg,
    TRY_CAST(json_extract(p.value, '$.compressor_te_evaporator_temp') AS DOUBLE) AS te,
    TRY_CAST(json_extract(p.value, '$.compressor_evo_outdoor_expansion_valve_opening') AS DOUBLE) AS evo,
    TRY_CAST(json_extract(p.value, '$.outdoor_temp') AS DOUBLE)                  AS outdoor,
    TRY_CAST(json_extract(p.value, '$.compressor_frequency') AS DOUBLE)          AS freq,
    json_extract_string(p.value, '$.operation_state')                            AS op_state
  FROM read_json(
         's3://hitachi-telemetry-archive/metrics/year=$Y/month=$M/day=$D/batch_*.json',
         columns = {instance_hash: 'VARCHAR', points: 'JSON'}
       ),
       json_each(points) AS p
  WHERE TRY_CAST(json_extract(p.value, '$.compressor_frequency') AS DOUBLE) > 0
    AND COALESCE(TRY_CAST(json_extract(p.value, '$.is_defrosting') AS BOOLEAN), false) = false
) TO '$OUT' (HEADER, DELIMITER ',');
"
  echo "$DAY: $(($(wc -l < "$OUT") - 1)) running-points"
done
