import { describe, expect, it, vi } from "vitest";

import worker from "../src/index";
import {
  STATS_KEY,
  computeStats,
  previousUtcDay,
  publishStats,
  type FleetStats,
  type SqlRunner,
} from "../src/stats";
import type { Env } from "../src/types";

/** Fake AE SQL: answers by the column the query groups on. */
function fakeRunner(): { run: SqlRunner; queries: string[] } {
  const queries: string[] = [];
  const byColumn: Record<string, Record<string, unknown>[]> = {
    blob1: [{ value: "2.2.0", n: "3" }, { value: "2.1.6", n: 1 }],
    blob2: [{ value: "2026.10.1", n: 4 }],
    blob3: [{ value: "Cfb", n: 3 }, { value: "", n: 1 }],
    blob4: [{ value: "yutaki_s", n: 4 }, { value: "yutaki_m", n: 1 }],
    blob5: [{ value: "modbus_atw_mbs_02", n: 5 }],
    blob6: [{ value: "single", n: 5 }, { value: "three", n: 0 }],
    double5: [{ value: 1, n: 4 }, { value: 2, n: 1 }],
  };
  const run: SqlRunner = async (sql) => {
    queries.push(sql);
    if (sql.includes("AS installs")) {
      return [{ installs: "4", units: "5", has_dhw: 3, has_pool: 0, has_cooling: 2, has_secondary_compressor: 1 }];
    }
    const column = /SELECT (\w+) AS value/.exec(sql)?.[1] ?? "";
    return byColumn[column] ?? [];
  };
  return { run, queries };
}

describe("previousUtcDay", () => {
  it("returns the day before, in UTC", () => {
    expect(previousUtcDay(Date.parse("2026-10-12T00:30:00Z"))).toBe("2026-10-11");
    expect(previousUtcDay(Date.parse("2026-03-01T00:30:00Z"))).toBe("2026-02-28");
  });
});

describe("computeStats", () => {
  it("publishes one distribution per dimension, never a combination", async () => {
    const { run, queries } = fakeRunner();
    const stats = await computeStats(run, "2026-10-11", null, new Date("2026-10-12T00:30:00Z"));

    expect(stats.active_installs).toBe(4);
    expect(stats.units).toBe(5);
    expect(stats.distributions.integration_version).toEqual({ "2.2.0": 3, "2.1.6": 1 });
    expect(stats.distributions.climate_zone).toEqual({ Cfb: 3, unknown: 1 });
    expect(stats.distributions.max_circuits).toEqual({ "1": 4, "2": 1 });
    // Zero counts are dropped.
    expect(stats.distributions.power_supply).toEqual({ single: 5 });
    expect(stats.capabilities).toEqual({ has_dhw: 3, has_pool: 0, has_cooling: 2, has_secondary_compressor: 1 });
    expect(stats.history).toEqual([{ date: "2026-10-11", active_installs: 4, units: 5 }]);

    // Every grouped query groups on a single column, restricted to the day.
    for (const sql of queries.filter((q) => q.includes("GROUP BY"))) {
      expect(sql).toMatch(/GROUP BY value /);
      expect(sql).toContain("toDateTime('2026-10-11 00:00:00')");
      expect(sql).toContain("toDateTime('2026-10-12 00:00:00')");
    }
    // Installation-level dimensions are weighted by double1.
    expect(queries.find((q) => q.includes("blob1"))).toContain("SUM(_sample_interval * double1)");
  });

  it("appends to the history, replacing a recomputed day", async () => {
    const { run } = fakeRunner();
    const previous = {
      history: [
        { date: "2026-10-10", active_installs: 2, units: 2 },
        { date: "2026-10-11", active_installs: 1, units: 1 },
      ],
    } as FleetStats;
    const stats = await computeStats(run, "2026-10-11", previous);
    expect(stats.history).toEqual([
      { date: "2026-10-10", active_installs: 2, units: 2 },
      { date: "2026-10-11", active_installs: 4, units: 5 },
    ]);
  });

  it("refuses a malformed day (it lands in SQL)", async () => {
    const { run } = fakeRunner();
    await expect(computeStats(run, "2026-10-11'; DROP", null)).rejects.toThrow(/invalid day/);
  });
});

function r2(stored: Map<string, string>) {
  return {
    get: vi.fn(async (key: string) => {
      const value = stored.get(key);
      return value === undefined
        ? null
        : { body: new Response(value).body, json: async () => JSON.parse(value) };
    }),
    put: vi.fn(async (key: string, value: string) => {
      stored.set(key, value);
    }),
    delete: vi.fn(),
  };
}

function env(bucket: ReturnType<typeof r2>): Env {
  return {
    ARCHIVE: bucket as unknown as R2Bucket,
    AE: { writeDataPoint: vi.fn() } as unknown as AnalyticsEngineDataset,
    PING: { writeDataPoint: vi.fn() } as unknown as AnalyticsEngineDataset,
  };
}

describe("publish and serve", () => {
  it("publishes to R2 and serves it with open CORS", async () => {
    const stored = new Map<string, string>();
    const e = env(r2(stored));
    await publishStats(e, "2026-10-11", fakeRunner().run);
    expect(stored.has(STATS_KEY)).toBe(true);

    const res = await worker.fetch(new Request("https://telemetry.internal/v1/stats"), e);
    expect(res.status).toBe(200);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
    expect(((await res.json()) as FleetStats).active_installs).toBe(4);
  });

  it("does not publish a day without pings", async () => {
    const stored = new Map<string, string>();
    const e = env(r2(stored));
    await publishStats(e, "2026-10-11", fakeRunner().run);
    const published = stored.get(STATS_KEY);

    const empty: SqlRunner = async (sql) => (sql.includes("AS installs") ? [{ installs: 0, units: 0 }] : []);
    expect(await publishStats(e, "2026-10-12", empty)).toBeNull();
    expect(stored.get(STATS_KEY)).toBe(published);
  });

  it("drops zero days left in the history", async () => {
    const { run } = fakeRunner();
    const previous = { history: [{ date: "2026-10-10", active_installs: 0, units: 0 }] } as FleetStats;
    const stats = await computeStats(run, "2026-10-11", previous);
    expect(stats.history.map((h) => h.date)).toEqual(["2026-10-11"]);
  });

  it("answers 404 before the first publication", async () => {
    const res = await worker.fetch(new Request("https://telemetry.internal/v1/stats"), env(r2(new Map())));
    expect(res.status).toBe(404);
  });

  it("fails loudly without the SQL API credentials", async () => {
    await expect(publishStats(env(r2(new Map())), "2026-10-11")).rejects.toThrow(/AE_API_TOKEN/);
  });
});
