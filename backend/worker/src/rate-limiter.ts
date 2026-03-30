/**
 * Per-instance-hash + payload-type rate limiting using Cloudflare Cache API.
 * Limit: 1 request per minute per (instance_hash, payload_type).
 *
 * Uses the Cache API instead of KV to avoid KV write operation limits
 * (free tier: 1,000 writes/day). The Cache API has no such limits.
 *
 * Keying by type allows different payload types (installation, metrics,
 * snapshot, daily_stats) to be sent concurrently without blocking each other.
 *
 * Note: Cache API is per-colo, so rate limiting is not globally consistent.
 * This is acceptable — slight leakage across colos is fine for telemetry.
 */

const WINDOW_SECONDS = 60;

/** Synthetic origin used for cache keys (never actually fetched). */
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
  const cacheKey = new Request(`${CACHE_KEY_PREFIX}${instanceHash}/${payloadType}`);

  const cached = await cache.match(cacheKey);

  if (cached) {
    const lastRequest = parseInt(await cached.text(), 10);
    const now = Math.floor(Date.now() / 1000);
    const elapsed = now - lastRequest;
    if (elapsed < WINDOW_SECONDS) {
      throw new RateLimitError(WINDOW_SECONDS - elapsed);
    }
  }

  // Store current timestamp with TTL
  const now = String(Math.floor(Date.now() / 1000));
  const response = new Response(now, {
    headers: {
      "Cache-Control": `max-age=${WINDOW_SECONDS}`,
    },
  });
  await cache.put(cacheKey, response);
}
