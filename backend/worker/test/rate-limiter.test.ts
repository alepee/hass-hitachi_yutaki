import { beforeEach, describe, expect, it, vi } from "vitest";

import { isRateLimited, markRateLimit } from "../src/rate-limiter";

/**
 * Minimal in-memory fake of the Cloudflare Cache API (`caches.default`).
 * Backed by a Map. `put` records calls so tests can assert that a
 * read-only check never writes.
 */
function createFakeCache() {
  const store = new Map<string, Response>();
  return {
    store,
    put: vi.fn(async (key: RequestInfo | URL, response: Response) => {
      store.set(String(key), response);
    }),
    match: vi.fn(async (key: RequestInfo | URL) => store.get(String(key))),
  };
}

let fakeCache: ReturnType<typeof createFakeCache>;

beforeEach(() => {
  fakeCache = createFakeCache();
  // @ts-expect-error — assign a minimal fake onto the global caches binding
  globalThis.caches = { default: fakeCache };
});

const HASH = "a".repeat(64);

describe("isRateLimited", () => {
  it("returns false on a cold key and does NOT write to the cache", async () => {
    const limited = await isRateLimited(HASH, "metrics");

    expect(limited).toBe(false);
    expect(fakeCache.put).not.toHaveBeenCalled();
    expect(fakeCache.store.size).toBe(0);
  });

  it("returns true after markRateLimit for the same (hash, type)", async () => {
    await markRateLimit(HASH, "metrics");

    expect(await isRateLimited(HASH, "metrics")).toBe(true);
  });

  it("namespaces by (instance_hash, payload_type)", async () => {
    await markRateLimit(HASH, "metrics");

    expect(await isRateLimited(HASH, "metrics")).toBe(true);
    expect(await isRateLimited(HASH, "snapshot")).toBe(false);
  });
});
