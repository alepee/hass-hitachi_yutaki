/**
 * R2 archive — writes JSON payloads as individual files (single sink).
 * Hive-style partitioning for DuckDB/Parquet compatibility.
 *
 * Metrics batches and snapshots, the bulk of the archive, are stored gzipped
 * (`.json.gz`): about 10x smaller, which keeps the R2 bill in check. Objects
 * written before this change stay plain `.json`; a `*.json*` glob matches
 * both, and DuckDB detects the compression from the extension.
 *
 * File layout, legacy (no explicit device_hash, <hash> = instance only):
 *   metrics/year=2026/month=03/day=13/batch_<ts>_<rand>_<hash>.json.gz
 *   snapshots/year=2026/month=03/day=13/snap_<ts>_<rand>_<hash>.json.gz
 *   daily_stats/year=2026/month=03/daily_<date>_<hash>.json
 *   installations/install_<hash>.json
 *
 * File layout, with an explicit device_hash (<hash> = <instance>_<device>):
 *   metrics/year=2026/month=03/day=13/batch_<ts>_<rand>_<instance>_<device>.json.gz
 *   snapshots/year=2026/month=03/day=13/snap_<ts>_<rand>_<instance>_<device>.json.gz
 *   daily_stats/year=2026/month=03/daily_<date>_<instance>_<device>.json
 *   installations/install_<instance>_<device>.json
 */

import type {
  DailyStatsPayload,
  MetricsPayload,
  SnapshotPayload,
  TelemetryPayload,
} from "./types";

function dateParts(isoDate?: string): { year: string; month: string; day: string } {
  const parsed = isoDate ? new Date(isoDate) : new Date();
  // An unparseable date makes every component NaN, which would archive the
  // object under `year=NaN/month=NaN/day=NaN/`: invisible to every
  // date-partitioned scan and enough to break a typed hive-partitioned read of
  // the whole tree. Fall back to ingestion time instead of rejecting, since the
  // payload itself is still usable data (#414).
  const d = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
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
 * Payloads carrying a device_hash gain the unit component, which is what
 * separates two entries of one instance (#395).
 */
function hashSuffix(payload: TelemetryPayload, hasExplicitDeviceHash: boolean): string {
  const instance = shortHash(payload.instance_hash);
  return hasExplicitDeviceHash
    ? `${instance}_${shortHash(payload.device_hash)}`
    : instance;
}

/**
 * Random component for append-only object names.
 *
 * The unit component above separates two *entries*; this separates two batches
 * of the same entry. The timestamp alone has one-second resolution, so two of
 * them in the same second computed the same key and the second `put` silently
 * replaced the first. The rate limiter makes that unlikely, not impossible:
 * the Cache API is per-colo, so two requests reaching two colos can both pass
 * `isRateLimited` (a leak the limiter documents as acceptable, on the
 * assumption that an extra accepted request is harmless). It is harmless only
 * if it does not overwrite anything (#414).
 *
 * Placed before the suffix so a name still *ends* with the hash, which is what
 * the documented way of matching an object to an installation relies on.
 */
function nonce(): string {
  return crypto.randomUUID().slice(0, 8);
}

/**
 * Payload types stored gzipped. Installations are overwritten current-state
 * documents and daily stats are legacy: both are small, so they stay plain.
 */
function isCompressed(payload: TelemetryPayload): boolean {
  return payload.type === "metrics" || payload.type === "snapshot";
}

async function gzip(text: string): Promise<ArrayBuffer> {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Response(stream).arrayBuffer();
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
  const json = JSON.stringify(payload);
  const compressed = isCompressed(payload);
  const key = buildKey(payload, hasExplicitDeviceHash) + (compressed ? ".gz" : "");
  // No Content-Encoding: readers get the gzip bytes as stored, and the
  // extension tells them how to decode, the same over S3 and the REST API.
  await bucket.put(key, compressed ? await gzip(json) : json, {
    httpMetadata: { contentType: compressed ? "application/gzip" : "application/json" },
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
      return `metrics/year=${year}/month=${month}/day=${day}/batch_${ts}_${nonce()}_${suffix}.json`;
    }
    case "daily_stats": {
      const { year, month } = dateParts((payload as DailyStatsPayload).date);
      return `daily_stats/year=${year}/month=${month}/daily_${(payload as DailyStatsPayload).date}_${suffix}.json`;
    }
    case "snapshot": {
      // The validator guarantees a parseable `time` (#442), so body and
      // partition agree; `dateParts` still guards against the impossible.
      const { year, month, day } = dateParts((payload as SnapshotPayload).time);
      return `snapshots/year=${year}/month=${month}/day=${day}/snap_${ts}_${nonce()}_${suffix}.json`;
    }
  }
}
