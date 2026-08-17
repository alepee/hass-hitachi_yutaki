/**
 * R2 archive — writes JSON payloads as individual files (single sink).
 * Hive-style partitioning for DuckDB/Parquet compatibility.
 *
 * File layout — legacy (no explicit device_hash, <hash> = instance only):
 *   metrics/year=2026/month=03/day=13/batch_<ts>_<hash>.json
 *   snapshots/year=2026/month=03/day=13/snap_<ts>_<hash>.json
 *   daily_stats/year=2026/month=03/daily_<date>_<hash>.json
 *   installations/install_<hash>.json
 *
 * File layout — with an explicit device_hash (<hash> = <instance>_<device>):
 *   metrics/year=2026/month=03/day=13/batch_<ts>_<instance>_<device>.json
 *   snapshots/year=2026/month=03/day=13/snap_<ts>_<instance>_<device>.json
 *   daily_stats/year=2026/month=03/daily_<date>_<instance>_<device>.json
 *   installations/install_<instance>_<device>.json
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
 * Object-name suffix. Legacy payloads (no explicit device_hash) keep the
 * historical instance-only form so their objects stay at the same keys.
 * Payloads carrying a device_hash gain the unit component, which is also what
 * stops two entries of one instance from colliding on the same second (#395).
 */
function hashSuffix(payload: TelemetryPayload, hasExplicitDeviceHash: boolean): string {
  const instance = shortHash(payload.instance_hash);
  return hasExplicitDeviceHash
    ? `${instance}_${shortHash(payload.device_hash)}`
    : instance;
}

/**
 * Archive a validated payload to R2 — the single sink for telemetry.
 * Throws on R2 failure; the request handler returns 502 in that case.
 */
export async function archiveToR2(
  bucket: R2Bucket,
  payload: TelemetryPayload,
  hasExplicitDeviceHash: boolean,
): Promise<void> {
  const body = JSON.stringify(payload);
  const key = buildKey(payload, hasExplicitDeviceHash);
  await bucket.put(key, body, {
    httpMetadata: { contentType: "application/json" },
    customMetadata: {
      instance_hash: payload.instance_hash,
      device_hash: payload.device_hash,
      type: payload.type,
    },
  });
}

/**
 * Delete the pre-#395 installation object for an instance.
 *
 * That key was a single overwritten current-state document. Once a client
 * sends a device_hash it writes to the new key and never touches the old one
 * again, which would leave a stale object double-counting in a scan of
 * `installations/`. Best-effort and idempotent: the archive write is the
 * contract, so a delete failure must not fail the request.
 */
export async function sweepLegacyInstallation(
  bucket: R2Bucket,
  instanceHash: string,
): Promise<void> {
  await bucket.delete(`installations/install_${shortHash(instanceHash)}.json`);
}

function buildKey(payload: TelemetryPayload, hasExplicitDeviceHash: boolean): string {
  const suffix = hashSuffix(payload, hasExplicitDeviceHash);
  const ts = Math.floor(Date.now() / 1000);

  switch (payload.type) {
    case "installation":
      return `installations/install_${suffix}.json`;
    case "metrics": {
      const firstTime = (payload as MetricsPayload).points[0]?.time;
      const { year, month, day } = dateParts(firstTime);
      return `metrics/year=${year}/month=${month}/day=${day}/batch_${ts}_${suffix}.json`;
    }
    case "daily_stats": {
      const { year, month } = dateParts((payload as DailyStatsPayload).date);
      return `daily_stats/year=${year}/month=${month}/daily_${(payload as DailyStatsPayload).date}_${suffix}.json`;
    }
    case "snapshot": {
      const { year, month, day } = dateParts();
      return `snapshots/year=${year}/month=${month}/day=${day}/snap_${ts}_${suffix}.json`;
    }
  }
}
