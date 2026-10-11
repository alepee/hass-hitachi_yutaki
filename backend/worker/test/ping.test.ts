import { describe, expect, it, vi } from "vitest";

import worker from "../src/index";
import { validatePing } from "../src/ping";
import type { Env } from "../src/types";

function unit(overrides: Record<string, unknown> = {}) {
  return {
    profile: "yutaki_s80",
    gateway_type: "modbus_atw_mbs_02",
    power_supply: "three",
    has_dhw: true,
    has_pool: false,
    has_cooling: true,
    max_circuits: 2,
    has_secondary_compressor: true,
    ...overrides,
  };
}

function ping(overrides: Record<string, unknown> = {}) {
  return {
    type: "ping",
    integration_version: "2.2.0",
    ha_version: "2026.10.1",
    climate_zone: "Cfb",
    units: [unit()],
    ...overrides,
  };
}

function makeEnv() {
  const ping = { writeDataPoint: vi.fn() };
  const bucket = { put: vi.fn(), get: vi.fn(), delete: vi.fn() };
  const env = {
    ARCHIVE: bucket as unknown as R2Bucket,
    AE: { writeDataPoint: vi.fn() } as unknown as AnalyticsEngineDataset,
    PING: ping as unknown as AnalyticsEngineDataset,
  } satisfies Env;
  return { env, ping, bucket };
}

function post(body: unknown): Request {
  return new Request("https://telemetry.internal/v1/ping", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("validatePing", () => {
  it("accepts a well-formed ping", () => {
    expect(validatePing(JSON.stringify(ping()))).toEqual(ping());
  });

  it("accepts a missing climate zone", () => {
    expect(validatePing(JSON.stringify(ping({ climate_zone: null }))).climate_zone).toBeNull();
  });

  it.each([
    ["an identifier", { instance_hash: "a".repeat(64) }],
    ["coordinates", { latitude: 48 }],
  ])("rejects %s at the top level", (_label, extra) => {
    expect(() => validatePing(JSON.stringify(ping(extra)))).toThrow(/unknown field/);
  });

  it("rejects an unknown unit field", () => {
    const body = ping({ units: [unit({ serial: "X" })] });
    expect(() => validatePing(JSON.stringify(body))).toThrow(/unknown field/);
  });

  it.each([
    ["no units", { units: [] }],
    ["too many units", { units: Array.from({ length: 17 }, () => unit()) }],
    ["a bad version", { ha_version: "<script>" }],
    ["a bad zone", { climate_zone: "Paris" }],
    ["a bad type", { type: "installation" }],
  ])("rejects %s", (_label, overrides) => {
    expect(() => validatePing(JSON.stringify(ping(overrides)))).toThrow();
  });

  it.each([
    ["power_supply", { power_supply: "mono" }],
    ["max_circuits", { max_circuits: 3 }],
    ["has_dhw", { has_dhw: "yes" }],
    ["profile", { profile: "Yutaki S" }],
  ])("rejects a bad unit %s", (_label, overrides) => {
    const body = ping({ units: [unit(overrides)] });
    expect(() => validatePing(JSON.stringify(body))).toThrow();
  });

  it("rejects an oversized body", () => {
    expect(() => validatePing(" ".repeat(9000))).toThrow(/too large/);
  });
});

describe("POST /v1/ping", () => {
  it("writes one datapoint per unit, the first carrying the install weight", async () => {
    const { env, ping: dataset, bucket } = makeEnv();
    const body = ping({ units: [unit(), unit({ profile: "yutaki_m", has_secondary_compressor: false })] });

    const res = await worker.fetch(post(body), env);

    expect(res.status).toBe(202);
    expect(dataset.writeDataPoint).toHaveBeenCalledTimes(2);
    const [first, second] = dataset.writeDataPoint.mock.calls.map((c) => c[0]);
    expect(first.blobs).toEqual(["2.2.0", "2026.10.1", "Cfb", "yutaki_s80", "modbus_atw_mbs_02", "three"]);
    expect(first.doubles).toEqual([1, 1, 0, 1, 2, 1]);
    expect(second.doubles[0]).toBe(0);
    expect(second.blobs[3]).toBe("yutaki_m");
    // No index (no identity to sample on) and nothing archived in R2.
    expect(first.indexes).toBeUndefined();
    expect(bucket.put).not.toHaveBeenCalled();
  });

  it("is not rate limited (no identity to key on)", async () => {
    const { env, ping: dataset } = makeEnv();
    await worker.fetch(post(ping()), env);
    const res = await worker.fetch(post(ping()), env);
    expect(res.status).toBe(202);
    expect(dataset.writeDataPoint).toHaveBeenCalledTimes(2);
  });

  it("answers 400 to an invalid ping without writing", async () => {
    const { env, ping: dataset } = makeEnv();
    const res = await worker.fetch(post(ping({ device_hash: "c".repeat(64) })), env);
    expect(res.status).toBe(400);
    expect(dataset.writeDataPoint).not.toHaveBeenCalled();
  });

  it("accepts a gzipped body", async () => {
    const { env } = makeEnv();
    const gz = new Blob([JSON.stringify(ping())]).stream().pipeThrough(new CompressionStream("gzip"));
    const req = new Request("https://telemetry.internal/v1/ping", {
      method: "POST",
      headers: { "content-type": "application/json", "content-encoding": "gzip" },
      body: await new Response(gz).arrayBuffer(),
    });
    expect((await worker.fetch(req, env)).status).toBe(202);
  });

  it("refuses GET", async () => {
    const { env } = makeEnv();
    const res = await worker.fetch(new Request("https://telemetry.internal/v1/ping"), env);
    expect(res.status).toBe(405);
  });
});
