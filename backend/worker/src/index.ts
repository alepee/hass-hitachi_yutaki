/**
 * Cloudflare Worker — Telemetry ingestion endpoint for Hitachi Yutaki.
 *
 * POST /v1/ingest
 *   - Accepts gzipped or plain JSON
 *   - Validates and sanitizes payload (field whitelist)
 *   - Rate limits per instance_hash (1 req/min via KV)
 *   - Dual write: TigerData (hot, 30-day) + R2 (cold, permanent)
 *   - Returns 202 Accepted on success
 */

import { archiveToR2 } from "./archive";
import { classifyClimateZone } from "./climate";
import { getClient, writeDailyStats, writeInstallation, writeMetrics, writeSnapshot } from "./db";
import { RateLimitError, checkRateLimit } from "./rate-limiter";
import type { Env, TelemetryPayload } from "./types";
import { ValidationError, validate } from "./validator";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Only accept POST to /v1/ingest
    const url = new URL(request.url);
    if (url.pathname !== "/v1/ingest") {
      return new Response("Not Found", { status: 404 });
    }
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    try {
      // Decompress if gzipped, otherwise read as text
      let body: string;
      if (request.headers.get("content-encoding") === "gzip") {
        const ds = new DecompressionStream("gzip");
        const decompressed = request.body!.pipeThrough(ds);
        body = await new Response(decompressed).text();
      } else {
        body = await request.text();
      }

      // Validate and sanitize
      const instanceHashHeader = request.headers.get("x-instance-hash");
      const payload = validate(body, instanceHashHeader);

      // Rate limit (per instance_hash + payload type)
      await checkRateLimit(env.RATE_LIMIT, payload.instance_hash, payload.type);

      // Enrich installation payload with precise Köppen climate zone
      if (payload.type === "installation") {
        const zone = classifyClimateZone(payload.data.latitude, payload.data.longitude);
        if (zone) {
          payload.data.climate_zone = zone;
        }
      }

      // Dual write: hot (TigerData) + cold (R2)
      await writeToDatabase(env, payload);

      // R2 archive is fire-and-forget
      try {
        await archiveToR2(env.ARCHIVE, payload);
      } catch (err) {
        console.warn("R2 archive failed (non-fatal):", err);
      }

      return new Response(null, { status: 202 });
    } catch (err) {
      if (err instanceof ValidationError) {
        return new Response(err.message, { status: err.statusCode });
      }
      if (err instanceof RateLimitError) {
        return new Response("Rate limit exceeded", {
          status: 429,
          headers: { "Retry-After": String(err.retryAfter) },
        });
      }
      console.error("Ingestion error:", err);
      return new Response("Internal Server Error", { status: 500 });
    }
  },
} satisfies ExportedHandler<Env>;

async function writeToDatabase(env: Env, payload: TelemetryPayload): Promise<void> {
  const client = await getClient(env.DB.connectionString);
  try {
    switch (payload.type) {
      case "installation":
        await writeInstallation(client, payload);
        break;
      case "metrics":
        await writeMetrics(client, payload);
        break;
      case "daily_stats":
        await writeDailyStats(client, payload);
        break;
      case "snapshot":
        await writeSnapshot(client, payload);
        break;
    }
  } finally {
    await client.end();
  }
}
