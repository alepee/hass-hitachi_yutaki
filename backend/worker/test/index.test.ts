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

/** Fake Analytics Engine dataset; `fail` makes the write throw. */
function createFakeAE(opts: { fail?: boolean } = {}) {
  return {
    writeDataPoint: vi.fn(() => {
      if (opts.fail) {
        throw new Error("AE unavailable");
      }
    }),
  };
}

const HASH = "b".repeat(64);

/** A second identity: the per-unit hash a client sends alongside HASH (#395). */
const DEVICE = "c".repeat(64);

const LEGACY_INSTALL_KEY = `installations/install_${HASH.slice(0, 12)}.json`;

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

/** Hands back the AE fake so its writes can be asserted. */
function makeEnvWithAE(
  bucket: ReturnType<typeof createFakeBucket>,
  aeOpts: { fail?: boolean } = {},
) {
  const ae = createFakeAE(aeOpts);
  const env = {
    ARCHIVE: bucket as unknown as R2Bucket,
    AE: ae as unknown as AnalyticsEngineDataset,
  } satisfies Env;
  return { env, ae };
}

function installationPayload(data: Record<string, unknown> = {}) {
  return {
    type: "installation",
    instance_hash: HASH,
    data: {
      profile: "yutaki_s80",
      gateway_type: "modbus_atw_mbs_02",
      ha_version: "2026.8.0",
      integration_version: "2.2.0",
      power_supply: "single",
      has_dhw: true,
      has_pool: false,
      has_cooling: true,
      max_circuits: 2,
      has_secondary_compressor: true,
      latitude: 48.5,
      longitude: 2.5,
      ...data,
    },
  };
}

/** The key the bucket was asked to write, from the first `put` call. */
function writtenKey(bucket: ReturnType<typeof createFakeBucket>): string {
  return bucket.put.mock.calls[0][0] as unknown as string;
}

describe("hardening (#414)", () => {
  describe("a batch is never archived under a NaN partition", () => {
    it("falls back to ingestion time when the first point's time is unparseable", async () => {
      const bucket = createFakeBucket();
      const payload = {
        ...metricsPayload(),
        points: [{ time: "not-a-date", outdoor_temp: 5 }],
      };

      const res = await worker.fetch(makeRequest(payload), makeEnv(bucket));

      // Accepted, because the payload itself is usable data.
      expect(res.status).toBe(202);
      expect(writtenKey(bucket)).not.toContain("NaN");
      expect(writtenKey(bucket)).toMatch(
        /^metrics\/year=\d{4}\/month=\d{2}\/day=\d{2}\//,
      );
    });

    it("still partitions on the point's own date when it is valid", async () => {
      const bucket = createFakeBucket();

      await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

      expect(writtenKey(bucket)).toContain("metrics/year=2026/month=03/day=13/");
    });
  });

  describe("an oversized body is refused while reading, not after", () => {
    it("answers 413 on a body past the limit", async () => {
      const bucket = createFakeBucket();
      const payload = {
        ...metricsPayload(),
        points: [{ time: "2026-03-13T12:00:00Z", blob: "x".repeat(300 * 1024) }],
      };

      const res = await worker.fetch(makeRequest(payload), makeEnv(bucket));

      expect(res.status).toBe(413);
      expect(bucket.put).not.toHaveBeenCalled();
    });

    it("stops pulling from the stream instead of buffering it whole", async () => {
      // The point of the fix: a small gzip payload expanding to gigabytes must
      // not be materialised before anything rejects it. Counting how much of
      // the body the Worker actually pulls is what separates "refused while
      // reading" from "refused after buffering", which a status assertion
      // alone cannot tell apart.
      const CHUNK = 64 * 1024;
      let pulled = 0;
      const endless = new ReadableStream<Uint8Array>({
        pull(controller) {
          pulled += CHUNK;
          if (pulled > 64 * 1024 * 1024) {
            controller.close();
            return;
          }
          controller.enqueue(new Uint8Array(CHUNK).fill(120));
        },
      });
      const request = new Request("https://telemetry.internal/v1/ingest", {
        method: "POST",
        headers: { "content-type": "application/json", "x-instance-hash": HASH },
        body: endless,
        duplex: "half",
      } as RequestInit);

      const res = await worker.fetch(request, makeEnv(createFakeBucket()));

      expect(res.status).toBe(413);
      // A handful of chunks past the 256 KB limit, not 64 MB of them.
      expect(pulled).toBeLessThan(1024 * 1024);
    });

    it("accepts a body just under the limit", async () => {
      const bucket = createFakeBucket();
      const payload = {
        ...metricsPayload(),
        points: [{ time: "2026-03-13T12:00:00Z", blob: "x".repeat(200 * 1024) }],
      };

      const res = await worker.fetch(makeRequest(payload), makeEnv(bucket));

      expect(res.status).toBe(202);
    });
  });

  describe("installation fields of the wrong type are dropped, not archived", () => {
    it("drops a non-numeric latitude and still accepts the payload", async () => {
      const bucket = createFakeBucket();

      const res = await worker.fetch(
        makeRequest(installationPayload({ latitude: "fifty" })),
        makeEnv(bucket),
      );

      expect(res.status).toBe(202);
      const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
      expect(archived.data.latitude).toBeUndefined();
      expect(archived.data.profile).toBe("yutaki_s80");
    });

    it("keeps the Analytics Engine write alive when a field is malformed", async () => {
      // The AE catch is silent by design, so a throw there means an install
      // that exists in R2 and nowhere on the dashboard.
      const bucket = createFakeBucket();
      const { env, ae } = makeEnvWithAE(bucket);

      await worker.fetch(
        makeRequest(installationPayload({ max_circuits: "two" })),
        env,
      );

      expect(ae.writeDataPoint).toHaveBeenCalledTimes(1);
      const written = ae.writeDataPoint.mock.calls[0][0];
      expect(written.doubles.every((d: unknown) => typeof d === "number")).toBe(true);
    });

    it("drops a null where a number is expected", async () => {
      // Named for what it does: `JSON.stringify(Number.NaN)` emits `null`, so
      // this exercises the `typeof` branch, not the finite-number one.
      const bucket = createFakeBucket();

      await worker.fetch(
        makeRequest(installationPayload({ longitude: Number.NaN })),
        makeEnv(bucket),
      );

      const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
      expect(archived.data.longitude).toBeUndefined();
    });

    it("drops a number that overflowed to Infinity", async () => {
      // The finite-number guard is reachable over HTTP even though the JSON
      // grammar has no `Infinity` literal: an exponent that overflows parses
      // to it. `JSON.parse('{"latitude": 1e999}').latitude === Infinity`, a
      // number, so only the isFinite check stops it reaching the archive and
      // the Analytics Engine doubles.
      const bucket = createFakeBucket();
      const body = String.raw`{"type":"installation","instance_hash":"${HASH}",` +
        String.raw`"data":{"profile":"yutaki_s80","gateway_type":"modbus_atw_mbs_02",` +
        String.raw`"latitude":1e999,"max_circuits":2}}`;
      const request = new Request("https://telemetry.internal/v1/ingest", {
        method: "POST",
        headers: { "content-type": "application/json", "x-instance-hash": HASH },
        body,
      });

      const res = await worker.fetch(request, makeEnv(bucket));

      expect(res.status).toBe(202);
      const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
      expect(archived.data.latitude).toBeUndefined();
      expect(archived.data.max_circuits).toBe(2);
    });
  });

  describe("two batches in the same second no longer overwrite each other", () => {
    it("gives two identical payloads two distinct object names", async () => {
      const first = createFakeBucket();
      const second = createFakeBucket();

      await worker.fetch(makeRequest(metricsPayload()), makeEnv(first));
      // A second colo would not see the first request's rate-limit marker.
      fakeCache.store.clear();
      await worker.fetch(makeRequest(metricsPayload()), makeEnv(second));

      expect(writtenKey(first)).not.toBe(writtenKey(second));
    });

    it("keeps the instance hash at the end of the name", async () => {
      // Matching an object to an installation is documented as an ends-with on
      // the 12-char hash, so the random component goes before it.
      const bucket = createFakeBucket();

      await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

      expect(writtenKey(bucket).endsWith(`_${HASH.slice(0, 12)}.json`)).toBe(true);
    });

    it("leaves the installation object name stable", async () => {
      // That one is a current-state document: overwriting it is the point.
      const bucket = createFakeBucket();

      await worker.fetch(makeRequest(installationPayload()), makeEnv(bucket));

      expect(writtenKey(bucket)).toBe(`installations/install_${HASH.slice(0, 12)}.json`);
    });
  });

  describe("clients in the field keep working unchanged", () => {
    it("accepts the exact payload shape the released integration sends", async () => {
      const bucket = createFakeBucket();
      const { env, ae } = makeEnvWithAE(bucket);

      const install = await worker.fetch(makeRequest(installationPayload()), env);
      fakeCache.store.clear();
      const metrics = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

      expect(install.status).toBe(202);
      expect(metrics.status).toBe(202);
      expect(ae.writeDataPoint).toHaveBeenCalledTimes(1);
      const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
      expect(archived.data).toMatchObject({
        profile: "yutaki_s80",
        gateway_type: "modbus_atw_mbs_02",
        latitude: 48.5,
        longitude: 2.5,
        max_circuits: 2,
        has_dhw: true,
      });
    });

    it("accepts a gzipped body, which is how the integration sends", async () => {
      const bucket = createFakeBucket();
      const json = JSON.stringify(metricsPayload());
      const gzipped = new Response(
        new Blob([json]).stream().pipeThrough(new CompressionStream("gzip")),
      );
      const request = new Request("https://telemetry.internal/v1/ingest", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "content-encoding": "gzip",
          "x-instance-hash": HASH,
        },
        body: await gzipped.arrayBuffer(),
      });

      const res = await worker.fetch(request, makeEnv(bucket));

      expect(res.status).toBe(202);
    });

    it("still omits an absent optional field rather than inventing one", async () => {
      const bucket = createFakeBucket();
      const payload = installationPayload();
      delete (payload.data as Record<string, unknown>).latitude;

      await worker.fetch(makeRequest(payload), makeEnv(bucket));

      const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
      expect("latitude" in archived.data).toBe(false);
    });
  });
});

describe("Analytics Engine layout — the contract with the Grafana dashboard", () => {
  // Blobs and doubles are positional and the dashboard is not versioned in this
  // repo, so a swap here silently corrupts every panel and cannot be repaired
  // retroactively: the rows are already written. These assertions mirror the
  // base query documented in backend/README.md, position by position.
  it("emits every blob at the position the dashboard reads", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());

    await worker.fetch(
      makeRequest(
        installationPayload({ climate_zone: undefined, latitude: 48.5, longitude: 2.5 }),
      ),
      env,
    );

    const [point] = ae.writeDataPoint.mock.calls[0];
    expect(point.indexes).toEqual([HASH]);
    expect(point.blobs[0]).toBe(HASH); // blob1 instance_hash
    expect(point.blobs[1]).toBe("yutaki_s80"); // blob2 profile
    expect(point.blobs[2]).toBe("modbus_atw_mbs_02"); // blob3 gateway_type
    expect(point.blobs[3]).toBe("single"); // blob4 power_supply
    expect(point.blobs[4]).toBe("2.2.0"); // blob5 integration_version
    expect(point.blobs[5]).toBe("2026.8.0"); // blob6 ha_version
    expect(point.blobs[6]).toBe("Cfb"); // blob7 climate_zone, enriched worker-side
  });

  it("emits every double at the position the dashboard reads", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());

    await worker.fetch(makeRequest(installationPayload()), env);

    const [point] = ae.writeDataPoint.mock.calls[0];
    expect(point.doubles[0]).toBe(1); // double1 has_dhw
    expect(point.doubles[1]).toBe(0); // double2 has_pool
    expect(point.doubles[2]).toBe(1); // double3 has_cooling
    expect(point.doubles[3]).toBe(1); // double4 has_secondary_compressor
    expect(point.doubles[4]).toBe(2); // double5 max_circuits
    expect(point.doubles[5]).toBe(48.5); // double6 latitude
    expect(point.doubles[6]).toBe(2.5); // double7 longitude
    expect(point.doubles).toHaveLength(7);
  });

  it("substitutes rather than shifts when an optional field is missing", async () => {
    // A missing value must not move the ones after it.
    const bucket = createFakeBucket();
    const { env, ae } = makeEnvWithAE(bucket);
    const payload = installationPayload();
    for (const key of ["power_supply", "integration_version", "ha_version"]) {
      delete (payload.data as Record<string, unknown>)[key];
    }
    delete (payload.data as Record<string, unknown>).latitude;
    delete (payload.data as Record<string, unknown>).longitude;

    await worker.fetch(makeRequest(payload), env);

    const [point] = ae.writeDataPoint.mock.calls[0];
    expect(point.blobs[3]).toBe("");
    expect(point.blobs[4]).toBe("");
    expect(point.blobs[5]).toBe("");
    expect(point.blobs[6]).toBe(""); // no coordinates, so no climate zone
    expect(point.doubles[4]).toBe(2); // max_circuits still at its position
    expect(point.doubles[5]).toBe(0);
    expect(point.doubles[6]).toBe(0);
  });

  it("enriches the climate zone from the coordinates", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());

    await worker.fetch(
      makeRequest(installationPayload({ latitude: 48.5, longitude: 2.5 })),
      env,
    );

    const [point] = ae.writeDataPoint.mock.calls[0];
    expect(point.blobs[6]).toBe("Cfb");
  });

  it("writes nothing to Analytics Engine for a non-installation payload", async () => {
    const { env, ae } = makeEnvWithAE(createFakeBucket());

    await worker.fetch(makeRequest(metricsPayload()), env);

    expect(ae.writeDataPoint).not.toHaveBeenCalled();
  });
});

describe("secondary sinks must never change the response", () => {
  // The same defect class #324 fixed: a failure in a sink that is not the
  // contract turning into a client-visible error, hence a retry and a double
  // write. R2 is the contract; the rate-limit marker and Analytics Engine are
  // not. Both catches are deliberately silent, so nothing but a failing fake
  // can prove they are still there.
  it("still answers 202 when the Analytics Engine write throws", async () => {
    const bucket = createFakeBucket();
    const { env, ae } = makeEnvWithAE(bucket, { fail: true });

    const res = await worker.fetch(makeRequest(installationPayload()), env);

    expect(res.status).toBe(202);
    expect(ae.writeDataPoint).toHaveBeenCalledTimes(1);
    expect(bucket.put).toHaveBeenCalledTimes(1);
  });

  it("still answers 202 when committing the rate-limit marker fails", async () => {
    const bucket = createFakeBucket();
    fakeCache.put.mockRejectedValueOnce(new Error("cache unavailable"));

    const res = await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

    expect(res.status).toBe(202);
    expect(bucket.put).toHaveBeenCalledTimes(1);
  });
});

describe("the rate-limit marker actually expires", () => {
  it("stores a marker whose lifetime is the advertised window", async () => {
    // The fake cache never expires anything, so a marker written with no TTL
    // (blocking a unit forever) or a zero one (no limiting at all) passes every
    // other test in this file while still answering Retry-After: 60.
    const bucket = createFakeBucket();

    await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

    const [[, stored]] = fakeCache.put.mock.calls;
    expect(stored.headers.get("cache-control")).toBe("max-age=60");
  });
});

describe("payload types that had no test at all", () => {
  // daily_stats and snapshot were never exercised end to end, so their
  // whitelists — the final anonymization step before permanent archival — were
  // deletable without a single failure.
  function dailyStatsPayload(data: Record<string, unknown> = {}) {
    return {
      type: "daily_stats",
      instance_hash: HASH,
      date: "2026-03-13",
      data: { outdoor_temp_avg: 7.5, cop_avg: 3.2, compressor_starts: 12, ...data },
    };
  }

  function snapshotPayload(registers: Record<string, unknown> = {}) {
    return {
      type: "snapshot",
      instance_hash: HASH,
      time: "2026-03-13T12:00:00Z",
      profile: "yutaki_s80",
      gateway_type: "modbus_atw_mbs_02",
      registers: { outdoor_temp: 5, water_inlet_temp: 35, ...registers },
    };
  }

  it("accepts a daily_stats payload and partitions it by its own date", async () => {
    const bucket = createFakeBucket();

    const res = await worker.fetch(makeRequest(dailyStatsPayload()), makeEnv(bucket));

    expect(res.status).toBe(202);
    expect(writtenKey(bucket)).toBe(
      `daily_stats/year=2026/month=03/daily_2026-03-13_${HASH.slice(0, 12)}.json`,
    );
  });

  it("strips unknown fields from daily_stats before archiving", async () => {
    const bucket = createFakeBucket();

    await worker.fetch(
      makeRequest(dailyStatsPayload({ postcode: "75011", owner: "someone" })),
      makeEnv(bucket),
    );

    const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
    expect(archived.data.postcode).toBeUndefined();
    expect(archived.data.owner).toBeUndefined();
    expect(archived.data.cop_avg).toBe(3.2);
  });

  it("accepts a snapshot payload and partitions it by ingestion date", async () => {
    const bucket = createFakeBucket();

    const res = await worker.fetch(makeRequest(snapshotPayload()), makeEnv(bucket));

    expect(res.status).toBe(202);
    expect(writtenKey(bucket)).toMatch(
      /^snapshots\/year=\d{4}\/month=\d{2}\/day=\d{2}\/snap_/,
    );
    expect(writtenKey(bucket).endsWith(`_${HASH.slice(0, 12)}.json`)).toBe(true);
  });

  it("keeps only finite numeric registers in a snapshot", async () => {
    const bucket = createFakeBucket();

    await worker.fetch(
      makeRequest(
        snapshotPayload({ serial: "SN-12345", nested: { a: 1 }, broken: null }),
      ),
      makeEnv(bucket),
    );

    const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
    expect(archived.registers.outdoor_temp).toBe(5);
    expect(archived.registers.serial).toBeUndefined();
    expect(archived.registers.nested).toBeUndefined();
    expect(archived.registers.broken).toBeUndefined();
  });

  it("rate-limits each payload type on its own window", async () => {
    const env = makeEnv(createFakeBucket());

    const first = await worker.fetch(makeRequest(metricsPayload()), env);
    const second = await worker.fetch(makeRequest(dailyStatsPayload()), env);
    const third = await worker.fetch(makeRequest(metricsPayload()), env);

    expect(first.status).toBe(202);
    expect(second.status).toBe(202); // a different type, so a different window
    expect(third.status).toBe(429); // same type inside the window
  });
});

describe("the identity gate", () => {
  it("rejects an instance_hash that is not a SHA-256 hex string", async () => {
    // The hash goes into R2 object keys and the Analytics Engine index, so an
    // arbitrary string here pollutes the archive's partitioning.
    const bucket = createFakeBucket();
    const request = new Request("https://telemetry.internal/v1/ingest", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...metricsPayload(), instance_hash: "../../etc/passwd" }),
    });

    const res = await worker.fetch(request, makeEnv(bucket));

    expect(res.status).toBe(400);
    expect(bucket.put).not.toHaveBeenCalled();
  });

  it("rejects a body whose instance_hash contradicts the header", async () => {
    const bucket = createFakeBucket();
    const request = new Request("https://telemetry.internal/v1/ingest", {
      method: "POST",
      headers: { "content-type": "application/json", "x-instance-hash": "a".repeat(64) },
      body: JSON.stringify(metricsPayload()), // body says HASH, header says a…a
    });

    const res = await worker.fetch(request, makeEnv(bucket));

    expect(res.status).toBe(400);
    expect(bucket.put).not.toHaveBeenCalled();
  });

  it("caps the number of points in one batch", async () => {
    // The remaining volume bound below the byte limit.
    const bucket = createFakeBucket();
    const points = Array.from({ length: 501 }, () => ({
      time: "2026-03-13T12:00:00Z",
      outdoor_temp: 5,
    }));

    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), points }),
      makeEnv(bucket),
    );

    expect(res.status).toBe(400);
    expect(bucket.put).not.toHaveBeenCalled();
  });

  it("keeps only primitive values inside a metrics point", async () => {
    const bucket = createFakeBucket();

    await worker.fetch(
      makeRequest({
        ...metricsPayload(),
        points: [
          { time: "2026-03-13T12:00:00Z", outdoor_temp: 5, nested: { secret: 1 } },
        ],
      }),
      makeEnv(bucket),
    );

    const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
    expect(archived.points[0].outdoor_temp).toBe(5);
    expect(archived.points[0].nested).toBeUndefined();
  });

  it("answers 400, not 500, on a body that is not JSON", async () => {
    const request = new Request("https://telemetry.internal/v1/ingest", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{not json",
    });

    const res = await worker.fetch(request, makeEnv(createFakeBucket()));

    expect(res.status).toBe(400);
  });

  it("answers 404 off the ingest path and 405 on the wrong method", async () => {
    const env = makeEnv(createFakeBucket());

    const wrongPath = await worker.fetch(
      new Request("https://telemetry.internal/", { method: "POST" }),
      env,
    );
    const wrongMethod = await worker.fetch(
      new Request("https://telemetry.internal/v1/ingest", { method: "GET" }),
      env,
    );

    expect(wrongPath.status).toBe(404);
    expect(wrongMethod.status).toBe(405);
  });
});

describe("object metadata", () => {
  it("tags every archived object with its identity and type", async () => {
    // customMetadata is what lets a bucket listing be filtered without opening
    // each object, so it is part of the archive's contract, not decoration.
    const bucket = createFakeBucket();

    await worker.fetch(makeRequest(metricsPayload()), makeEnv(bucket));

    const [, , options] = bucket.put.mock.calls[0];
    expect(options.customMetadata).toMatchObject({ instance_hash: HASH, type: "metrics" });
    expect(options.httpMetadata.contentType).toBe("application/json");
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
describe("device_hash absence (#414)", () => {
  it("treats an explicit null as absent rather than rejecting it", async () => {
    // A client serializing an optional field as `null` means the same thing as
    // omitting it. Rejecting turned that into a permanent 400 for every one of
    // its payloads, where the legacy identity is the documented behaviour.
    const bucket = createFakeBucket();

    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: null }),
      makeEnv(bucket),
    );

    expect(res.status).toBe(202);
    const archived = JSON.parse(bucket.put.mock.calls[0][1] as unknown as string);
    expect(archived.device_hash).toBe(HASH);
    expect(writtenKey(bucket).endsWith(`_${HASH.slice(0, 12)}.json`)).toBe(true);
  });

  it("keys the rate limit on the instance identity for a null device_hash", async () => {
    const bucket = createFakeBucket();

    await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: null }),
      makeEnv(bucket),
    );

    expect([...fakeCache.store.keys()]).toEqual([
      `https://rate-limit.internal/rl/${HASH}/metrics`,
    ]);
  });

  it("still rejects a device_hash of the wrong shape", async () => {
    const bucket = createFakeBucket();

    const res = await worker.fetch(
      makeRequest({ ...metricsPayload(), device_hash: "not-a-hash" }),
      makeEnv(bucket),
    );

    expect(res.status).toBe(400);
  });
});
