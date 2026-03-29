/**
 * Per-instance-hash + payload-type rate limiting using Cloudflare KV.
 * Limit: 1 request per minute per (instance_hash, payload_type).
 *
 * Keying by type allows different payload types (installation, metrics,
 * snapshot, daily_stats) to be sent concurrently without blocking each other.
 */

const WINDOW_SECONDS = 60;

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
  kv: KVNamespace,
  instanceHash: string,
  payloadType: string,
): Promise<void> {
  const key = `rl:${instanceHash}:${payloadType}`;
  const existing = await kv.get(key);

  if (existing !== null) {
    const lastRequest = parseInt(existing, 10);
    const elapsed = Math.floor(Date.now() / 1000) - lastRequest;
    if (elapsed < WINDOW_SECONDS) {
      throw new RateLimitError(WINDOW_SECONDS - elapsed);
    }
  }

  // Set current timestamp with TTL
  await kv.put(key, String(Math.floor(Date.now() / 1000)), {
    expirationTtl: WINDOW_SECONDS,
  });
}
