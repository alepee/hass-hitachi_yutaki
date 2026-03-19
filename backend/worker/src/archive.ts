/**
 * R2 cold archive — writes JSON payloads as individual files.
 * Hive-style partitioning for DuckDB/Parquet compatibility.
 *
 * File layout:
 *   metrics/year=2026/month=03/day=13/batch_<ts>_<hash>.json
 *   snapshots/year=2026/month=03/day=13/snap_<ts>_<hash>.json
 *   daily_stats/year=2026/month=03/daily_<date>_<hash>.json
 *   installations/install_<hash>.json
 *
 * Note: Files are stored as JSON initially. A scheduled worker or
 * external job can convert to Parquet for optimal query performance.
 */

import type {
  DailyStatsPayload,
  MetricsPayload,
  TelemetryPayload,
} from "./types";

function dateParts(isoDate?: string): { year: string; month: string; day: string } {
  const d = isoDate ? new Date(isoDate) : new Date();
  return {
    year: String(d.getUTCFullYear()),
    month: String(d.getUTCMonth() + 1).padStart(2, "0"),
    day: String(d.getUTCDate()).padStart(2, "0"),
  };
}

function shortHash(instanceHash: string): string {
  return instanceHash.slice(0, 12);
}

/**
 * Archive a validated payload to R2.
 * Fire-and-forget: caller should catch errors and log, not fail the request.
 */
export async function archiveToR2(
  bucket: R2Bucket,
  payload: TelemetryPayload,
): Promise<void> {
  const body = JSON.stringify(payload);
  const key = buildKey(payload);
  await bucket.put(key, body, {
    httpMetadata: { contentType: "application/json" },
    customMetadata: {
      instance_hash: payload.instance_hash,
      type: payload.type,
    },
  });
}

function buildKey(payload: TelemetryPayload): string {
  const hash = shortHash(payload.instance_hash);
  const ts = Math.floor(Date.now() / 1000);

  switch (payload.type) {
    case "installation": {
      return `installations/install_${hash}.json`;
    }
    case "metrics": {
      const firstTime = (payload as MetricsPayload).points[0]?.time;
      const { year, month, day } = dateParts(firstTime);
      return `metrics/year=${year}/month=${month}/day=${day}/batch_${ts}_${hash}.json`;
    }
    case "daily_stats": {
      const { year, month } = dateParts((payload as DailyStatsPayload).date);
      return `daily_stats/year=${year}/month=${month}/daily_${(payload as DailyStatsPayload).date}_${hash}.json`;
    }
    case "snapshot": {
      const { year, month, day } = dateParts();
      return `snapshots/year=${year}/month=${month}/day=${day}/snap_${ts}_${hash}.json`;
    }
  }
}
