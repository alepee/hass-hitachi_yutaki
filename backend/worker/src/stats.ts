/**
 * Public fleet stats (#468).
 *
 * A daily cron aggregates the previous UTC day of fleet pings into one JSON
 * document, served as is by GET /v1/stats and drawn by the public page.
 * Only one distribution per dimension is published, never a combination of
 * attributes, so no published number can single out an installation.
 */

import type { Env } from "./types";

export const STATS_KEY = "public/stats.json";
const DATASET = "hitachi_fleet_ping";
const HISTORY_MAX_DAYS = 730;

/** Dimensions counted per installation (published name → column). */
const INSTALL_DIMENSIONS: Record<string, string> = {
  integration_version: "blob1",
  ha_version: "blob2",
  climate_zone: "blob3",
};
/** Dimensions counted per unit. */
const UNIT_DIMENSIONS: Record<string, string> = {
  profile: "blob4",
  gateway_type: "blob5",
  power_supply: "blob6",
  max_circuits: "double5",
};
const CAPABILITIES: Record<string, string> = {
  has_dhw: "double2",
  has_pool: "double3",
  has_cooling: "double4",
  has_secondary_compressor: "double6",
};

export interface FleetStats {
  schema: 1;
  generated_at: string;
  date: string;
  active_installs: number;
  units: number;
  distributions: Record<string, Record<string, number>>;
  capabilities: Record<string, number>;
  history: { date: string; active_installs: number; units: number }[];
}

/** Runs one Analytics Engine SQL query and returns its rows. */
export type SqlRunner = (sql: string) => Promise<Record<string, unknown>[]>;

export function aeSqlRunner(env: Env): SqlRunner {
  return async (sql) => {
    if (!env.CF_ACCOUNT_ID || !env.AE_API_TOKEN) {
      throw new Error("CF_ACCOUNT_ID and AE_API_TOKEN must be set for fleet stats");
    }
    const res = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/analytics_engine/sql`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${env.AE_API_TOKEN}` },
        body: sql,
      },
    );
    if (!res.ok) {
      throw new Error(`Analytics Engine SQL failed (HTTP ${res.status}): ${await res.text()}`);
    }
    const json = (await res.json()) as { data?: Record<string, unknown>[] };
    return json.data ?? [];
  };
}

/** The UTC day before `time`, as YYYY-MM-DD. */
export function previousUtcDay(time: number): string {
  const d = new Date(time);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

function dayFilter(day: string): string {
  const next = new Date(`${day}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  const end = next.toISOString().slice(0, 10);
  return `timestamp >= toDateTime('${day} 00:00:00') AND timestamp < toDateTime('${end} 00:00:00')`;
}

/** Aggregate one UTC day of pings. `day` must be YYYY-MM-DD. */
export async function computeStats(
  run: SqlRunner,
  day: string,
  previous: FleetStats | null,
  now: Date = new Date(),
): Promise<FleetStats> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
    throw new Error(`invalid day: ${day}`);
  }
  const where = dayFilter(day);

  const capabilityColumns = Object.entries(CAPABILITIES)
    .map(([name, col]) => `SUM(_sample_interval * ${col}) AS ${name}`)
    .join(", ");
  const [totals = {}] = await run(
    `SELECT SUM(_sample_interval * double1) AS installs, SUM(_sample_interval) AS units, ${capabilityColumns} FROM ${DATASET} WHERE ${where}`,
  );

  const distributions: Record<string, Record<string, number>> = {};
  const dimensions: [string, string, string][] = [
    ...Object.entries(INSTALL_DIMENSIONS).map(
      ([name, col]) => [name, col, "_sample_interval * double1"] as [string, string, string],
    ),
    ...Object.entries(UNIT_DIMENSIONS).map(
      ([name, col]) => [name, col, "_sample_interval"] as [string, string, string],
    ),
  ];
  for (const [name, col, weight] of dimensions) {
    const rows = await run(
      `SELECT ${col} AS value, SUM(${weight}) AS n FROM ${DATASET} WHERE ${where} GROUP BY value ORDER BY n DESC`,
    );
    const counts: Record<string, number> = {};
    for (const row of rows) {
      const n = Number(row.n);
      if (n > 0) {
        counts[String(row.value) || "unknown"] = n;
      }
    }
    distributions[name] = counts;
  }

  const capabilities: Record<string, number> = {};
  for (const name of Object.keys(CAPABILITIES)) {
    capabilities[name] = Number(totals[name] ?? 0);
  }

  const activeInstalls = Number(totals.installs ?? 0);
  const units = Number(totals.units ?? 0);
  // Zero days are never published; drop any left by an earlier version.
  const history = (previous?.history ?? []).filter(
    (h) => h.date !== day && h.active_installs > 0,
  );
  history.push({ date: day, active_installs: activeInstalls, units });
  history.sort((a, b) => a.date.localeCompare(b.date));

  return {
    schema: 1,
    generated_at: now.toISOString(),
    date: day,
    active_installs: activeInstalls,
    units,
    distributions,
    capabilities,
    history: history.slice(-HISTORY_MAX_DAYS),
  };
}

/**
 * Cron entry point: aggregate `day` and publish it to R2.
 *
 * A day without a single ping is not published: the fleet is never really
 * empty, so it means pings were not received (before the first release, or an
 * ingestion outage). Publishing it would replace the page with zeros and leave
 * a false zero in the history. Returns null when nothing was published.
 */
export async function publishStats(
  env: Env,
  day: string,
  run: SqlRunner = aeSqlRunner(env),
): Promise<FleetStats | null> {
  const existing = await env.ARCHIVE.get(STATS_KEY);
  const previous = existing ? ((await existing.json()) as FleetStats) : null;
  const stats = await computeStats(run, day, previous);
  if (stats.active_installs === 0) {
    console.warn(`fleet stats: no ping on ${day}, keeping the published document`);
    return null;
  }
  await env.ARCHIVE.put(STATS_KEY, JSON.stringify(stats), {
    httpMetadata: { contentType: "application/json" },
  });
  return stats;
}

/** GET /v1/stats: the published document, readable from any origin. */
export async function serveStats(env: Env): Promise<Response> {
  const headers = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "public, max-age=3600",
  };
  const object = await env.ARCHIVE.get(STATS_KEY);
  if (!object) {
    return new Response(JSON.stringify({ error: "no stats published yet" }), {
      status: 404,
      headers,
    });
  }
  return new Response(object.body, { headers });
}
