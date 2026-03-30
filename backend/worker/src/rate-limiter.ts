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
 * Note: Cache API is per-colo (not globally consistent). A client routed to
 * a different colo could bypass the window. This is acceptable for telemetry
 * — slight leakage is harmless.
 */

const WINDOW_SECONDS = 60;

/** Synthetic origin for cache keys (never actually fetched externally). */
const CACHE_KEY_PREFIX = "https://rate-limit.internal/rl/";

export class RateLimitError extends Error {
  constructor(public retryAfter: number) {
    super("Rate limit exceeded");
  }
}

/**
 * Check and enforce rate limit for an instance hash + payload type.
 * Throws RateLimitError if the limit is exceeded.
 */
export async function checkRateLimit(
  instanceHash: string,
  payloadType: string,
): Promise<void> {
  const cache = caches.default;
  const cacheKey = `${CACHE_KEY_PREFIX}${instanceHash}/${payloadType}`;

  const cached = await cache.match(cacheKey);
  if (cached) {
    // Entry exists and hasn't expired — still within the rate limit window
    throw new RateLimitError(WINDOW_SECONDS);
  }

  // Mark this (instance, type) as seen for the next WINDOW_SECONDS
  await cache.put(
    cacheKey,
    new Response(null, {
      headers: { "Cache-Control": `max-age=${WINDOW_SECONDS}` },
    }),
  );
}
