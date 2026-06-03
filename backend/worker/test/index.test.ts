import { beforeEach, describe, expect, it, vi } from "vitest";

import worker from "../src/index";
import type { Env } from "../src/types";

/**
 * Minimal in-memory fake of the Cloudflare Cache API (`caches.default`).
 * Shared across requests within a test to mimic the per-colo cache.
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

/** Fake R2 bucket; `put` can be configured to throw to simulate an outage. */
function createFakeBucket(opts: { fail?: boolean } = {}) {
  return {
    put: vi.fn(async () => {
      if (opts.fail) {
        throw new Error("R2 unavailable");
      }
      return {} as R2Object;
    }),
  };
}

/** Fake Analytics Engine dataset. */
function createFakeAE() {
  return { writeDataPoint: vi.fn() };
}

const HASH = "b".repeat(64);

function makeEnv(bucket: ReturnType<typeof createFakeBucket>): Env {
  return {
    ARCHIVE: bucket as unknown as R2Bucket,
    AE: createFakeAE() as unknown as AnalyticsEngineDataset,
  };
}

function makeRequest(body: object): Request {
  return new Request("https://telemetry.internal/v1/ingest", {
    method: "POST",
    headers: { "content-type": "application/json", "x-instance-hash": HASH },
    body: JSON.stringify(body),
  });
}

function metricsPayload() {
  return {
    type: "metrics",
    instance_hash: HASH,
    points: [{ time: "2026-03-13T12:00:00Z", outdoor_temp: 5 }],
  };
}

let fakeCache: ReturnType<typeof createFakeCache>;

beforeEach(() => {
  fakeCache = createFakeCache();
  // @ts-expect-error — assign a minimal fake onto the global caches binding
  globalThis.caches = { default: fakeCache };
});

describe("fetch handler — rate limit + archive (#324)", () => {
  it("does NOT consume the rate-limit slot when the R2 archive fails", async () => {
    // First request: R2 is down -> 502, slot must be preserved.
    const failingBucket = createFakeBucket({ fail: true });
    const res1 = await worker.fetch(makeRequest(metricsPayload()), makeEnv(failingBucket));
    expect(res1.status).toBe(502);

    // Second request (same hash+type), R2 recovered -> must be accepted (202),
    // NOT rejected with 429. This is the regression guard for #324.
    const okBucket = createFakeBucket();
    const res2 = await worker.fetch(makeRequest(metricsPayload()), makeEnv(okBucket));
    expect(res2.status).toBe(202);
    expect(okBucket.put).toHaveBeenCalledTimes(1);
  });

  it("marks the slot after a successful archive (second identical request -> 429)", async () => {
    const bucket = createFakeBucket();
    const res1 = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    expect(res1.status).toBe(202);

    const res2 = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    expect(res2.status).toBe(429);
    expect(res2.headers.get("Retry-After")).toBe("60");
    // Only the first request reached R2.
    expect(bucket.put).toHaveBeenCalledTimes(1);
  });

  it("rejects an already-limited request without writing to R2", async () => {
    const bucket = createFakeBucket();

    // Pre-mark the slot (simulate a prior accepted request).
    await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    bucket.put.mockClear();

    const res = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    expect(res.status).toBe(429);
    expect(res.headers.get("Retry-After")).toBe("60");
    expect(bucket.put).not.toHaveBeenCalled();
  });
});
