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

/** Fake R2 bucket; `put`/`delete` can be configured to throw to simulate an outage. */
function createFakeBucket(opts: { fail?: boolean; deleteFails?: boolean } = {}) {
  return {
    put: vi.fn(async () => {
      if (opts.fail) {
        throw new Error("R2 unavailable");
      }
      return {} as R2Object;
    }),
    delete: vi.fn(async () => {
      if (opts.deleteFails) {
        throw new Error("R2 delete unavailable");
      }
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

/** Like makeEnv, but hands back the AE fake so its writes can be asserted. */
function makeEnvWithAE(bucket: ReturnType<typeof createFakeBucket>) {
  const ae = createFakeAE();
  const env = {
    ARCHIVE: bucket as unknown as R2Bucket,
    AE: ae as unknown as AnalyticsEngineDataset,
  } satisfies Env;
  return { env, ae };
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

const DEVICE = "c".repeat(64);

function installationPayload() {
  return {
    type: "installation",
    instance_hash: HASH,
    data: { profile: "yutaki_s80", gateway_type: "modbus_atw_mbs_02" },
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

describe("device_hash validation (#395)", () => {
  it("accepts a payload without device_hash (legacy client)", async () => {
    const bucket = createFakeBucket();
    const res = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    expect(res.status).toBe(202);
  });

  it("accepts a valid device_hash", async () => {
    const bucket = createFakeBucket();
    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(res.status).toBe(202);
  });

  it("rejects a malformed device_hash with 400", async () => {
    const bucket = createFakeBucket();
    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: "not-a-hash" }),
      makeEnv(bucket),
    );
    expect(res.status).toBe(400);
    expect(await res.text()).toContain("device_hash");
  });

  it("archives device_hash without leaking the internal flag", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    const archived = JSON.parse(bucket.put.mock.calls[0][1] as string);
    expect(archived.device_hash).toBe(DEVICE);
    expect(archived).not.toHaveProperty("hasExplicitDeviceHash");
    expect(archived).not.toHaveProperty("has_explicit_device_hash");
  });

  it("falls back to the instance identity for a legacy payload", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));
    const archived = JSON.parse(bucket.put.mock.calls[0][1] as string);
    expect(archived.device_hash).toBe(HASH);
  });
});

describe("per-unit rate limiting (#395)", () => {
  it("lets two units of one instance send within the same window", async () => {
    const env = makeEnv(createFakeBucket());
    const deviceB = "d".repeat(64);

    const first = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      env,
    );
    const second = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: deviceB }),
      env,
    );

    expect(first.status).toBe(202);
    expect(second.status).toBe(202);
  });

  it("still rate limits a single unit", async () => {
    const env = makeEnv(createFakeBucket());

    await worker.fetch(makeRequest({ ...metricsPayload(), device_hash: DEVICE }), env);
    const second = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      env,
    );

    expect(second.status).toBe(429);
  });

  it("still rate limits a legacy client against itself", async () => {
    const env = makeEnv(createFakeBucket());

    await worker.fetch(makeRequest(metricsPayload()), env);
    const second = await worker.fetch(makeRequest(metricsPayload()), env);

    expect(second.status).toBe(429);
  });
});

const LEGACY_INSTALL_KEY = `installations/install_${HASH.slice(0, 12)}.json`;

describe("R2 key layout (#395)", () => {
  it("keeps the legacy layout for a payload without device_hash", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(makeRequest(installationPayload()), makeEnv(bucket));
    expect(bucket.put.mock.calls[0][0]).toBe(LEGACY_INSTALL_KEY);
  });

  it("adds the device component when device_hash is explicit", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(bucket.put.mock.calls[0][0]).toBe(
      `installations/install_${HASH.slice(0, 12)}_${DEVICE.slice(0, 12)}.json`,
    );
  });

  it("separates two units of one instance in the metrics archive", async () => {
    const bucket = createFakeBucket();
    const env = makeEnv(bucket);
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      env,
    );
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: "d".repeat(64) }),
      env,
    );

    const [keyA, keyB] = bucket.put.mock.calls.map((c) => c[0] as string);
    expect(keyA).not.toBe(keyB);
  });

  it("sweeps the stale legacy installation object", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(bucket.delete).toHaveBeenCalledWith(LEGACY_INSTALL_KEY);
  });

  it("does not sweep for a legacy payload", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(makeRequest(installationPayload()), makeEnv(bucket));
    expect(bucket.delete).not.toHaveBeenCalled();
  });

  it("does not sweep for a metrics payload", async () => {
    const bucket = createFakeBucket();
    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(bucket.delete).not.toHaveBeenCalled();
  });

  it("still returns 202 when the sweep fails", async () => {
    const bucket = createFakeBucket({ deleteFails: true });
    const res = await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );
    expect(res.status).toBe(202);
  });
});

describe("WAE fleet dashboard (#395)", () => {
  it("keeps instance_hash as the index and blob1", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      env,
    );
    const point = ae.writeDataPoint.mock.calls[0][0];
    expect(point.indexes).toEqual([HASH]);
    expect(point.blobs[0]).toBe(HASH);
  });

  it("appends device_hash after climate_zone without shifting blobs", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());
    await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      env,
    );
    const point = ae.writeDataPoint.mock.calls[0][0];
    expect(point.blobs).toHaveLength(8);
    expect(point.blobs[1]).toBe("yutaki_s80");
    expect(point.blobs[7]).toBe(DEVICE);
  });

  it("falls back to instance_hash for a legacy payload", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());
    await worker.fetch(makeRequest(installationPayload()), env);
    const point = ae.writeDataPoint.mock.calls[0][0];
    expect(point.blobs[7]).toBe(HASH);
  });
});

describe("contracts the integration client depends on (#395)", () => {
  it("answers 413, not 400, when the body exceeds the payload limit", async () => {
    // The client drops a batch on 413 and re-queues it on any other 4xx. A
    // Worker that answered 400 here would make every oversized batch cycle
    // through the buffer instead of being discarded.
    const bucket = createFakeBucket();
    const oversized = {
      ...metricsPayload(),
      points: [{ time: "2026-03-13T12:00:00Z", blob: "x".repeat(300 * 1024) }],
    };

    const res = await worker.fetch(makeRequest(oversized), makeEnv(bucket));

    expect(res.status).toBe(413);
    expect(bucket.put).not.toHaveBeenCalled();
  });

  it("keeps the legacy rate-limit cache key byte-identical", async () => {
    // A client without device_hash must land on the exact key it used before
    // #395. A changed prefix or layout would reset every in-flight window on
    // deploy and double-accept payloads during that minute.
    const bucket = createFakeBucket();

    await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

    expect([...fakeCache.store.keys()]).toEqual([
      `https://rate-limit.internal/rl/${HASH}/metrics`,
    ]);
  });

  it("keys the rate limit on the device hash when one is sent", async () => {
    const bucket = createFakeBucket();

    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );

    expect([...fakeCache.store.keys()]).toEqual([
      `https://rate-limit.internal/rl/${DEVICE}/metrics`,
    ]);
  });

  it("does not sweep the legacy object when the archive fails", async () => {
    // Ordering guard: sweeping before a failed write would delete the only
    // remaining copy of that installation and answer 502 with nothing written.
    const bucket = createFakeBucket({ fail: true });

    const res = await worker.fetch(
      makeRequest({ ...installationPayload(), device_hash: DEVICE }),
      makeEnv(bucket),
    );

    expect(res.status).toBe(502);
    expect(bucket.delete).not.toHaveBeenCalled();
  });
});
