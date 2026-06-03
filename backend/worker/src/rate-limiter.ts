/**
 * Per-instance-hash + payload-type rate limiting using Cloudflare Cache API.
 * Limit: 1 request per minute per (instance_hash, payload_type).
 *
 * Uses the Cache API instead of KV to avoid KV operation limits
 * (free tier: 1,000 writes/day — exceeded with just 5 users).
 * The Cache API has no per-operation quotas.
 *
 * Keying by type allows different payload types (installation, metrics,
 * snapshot, daily_stats) to be sent concurrently without blocking each other.
 *
 * Contract — check then mark (split for #324):
 *   1. `isRateLimited()` is a read-only probe (no cache write). Call it before
 *      doing any expensive work to short-circuit a request that is already
 *      within the window.
 *   2. `markRateLimit()` commits the 60s marker. It is called ONLY after the
 *      durable R2 write has succeeded, so a transient R2 outage (502) never
 *      burns the slot — the client's retry within the window is accepted
 *      instead of being rejected with 429 (which previously caused guaranteed
 *      data loss for that (instance_hash, type)).
 *
 * Tradeoff: because the marker is committed after the archive, two
 * near-simultaneous requests can both pass `isRateLimited()` and both archive
 * before either marks, widening the window by at most one extra accepted
 * request. This is acceptable: the Cache API is per-colo (not globally
 * consistent) and best-effort by design, so slight leakage is already harmless
 * — and it is strictly preferable to dropping telemetry on a recoverable error.
 */

const WINDOW_SECONDS = 60;

/** Synthetic origin for cache keys (never actually fetched externally). */
const CACHE_KEY_PREFIX = "https://rate-limit.internal/rl/";

export class RateLimitError extends Error {
  constructor(public retryAfter: number) {
    super("Rate limit exceeded");
  }
}

/** Build the per-(instance, type) cache key. */
function cacheKeyFor(instanceHash: string, payloadType: string): string {
  return `${CACHE_KEY_PREFIX}${instanceHash}/${payloadType}`;
}

/**
 * Read-only check: is this (instance_hash, payload_type) currently within the
 * rate-limit window? Does NOT write to the cache. Run before archiving.
 */
export async function isRateLimited(
  instanceHash: string,
  payloadType: string,
): Promise<boolean> {
  const cache = caches.default;
  const cached = await cache.match(cacheKeyFor(instanceHash, payloadType));
  return cached !== undefined;
}

/**
 * Commit the rate-limit marker for the next WINDOW_SECONDS. Call this ONLY
 * after the payload has been durably archived, so a failed write never
 * consumes the slot.
 */
export async function markRateLimit(
  instanceHash: string,
  payloadType: string,
): Promise<void> {
  const cache = caches.default;
  await cache.put(
    cacheKeyFor(instanceHash, payloadType),
    new Response(null, {
      headers: { "Cache-Control": `max-age=${WINDOW_SECONDS}` },
    }),
  );
}

export { WINDOW_SECONDS };
