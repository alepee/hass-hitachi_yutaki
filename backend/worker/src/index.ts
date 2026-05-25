/**
 * Cloudflare Worker — Telemetry ingestion endpoint for Hitachi Yutaki.
 *
 * POST /v1/ingest
 *   - Accepts gzipped or plain JSON
 *   - Validates and sanitizes payload (field whitelist)
 *   - Rate limits per instance_hash (1 req/min via Cache API)
 *   - R2 (permanent JSON archive, partitioned Hive-style) — sole archive, all types
 *   - Analytics Engine (dataset hitachi_installations) — installation payloads only, for the fleet dashboard
 *   - Returns 202 Accepted on success, 502 Bad Gateway if R2 is unavailable
 */

import { archiveToR2 } from "./archive";
import { classifyClimateZone } from "./climate";
import { RateLimitError, checkRateLimit } from "./rate-limiter";
import type { Env } from "./types";
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
      await checkRateLimit(payload.instance_hash, payload.type);

      // Enrich installation payload with precise Köppen climate zone
      if (payload.type === "installation") {
        const zone = classifyClimateZone(payload.data.latitude, payload.data.longitude);
        if (zone) {
          payload.data.climate_zone = zone;
        }
      }

      try {
        await archiveToR2(env.ARCHIVE, payload);
      } catch (err) {
        console.error("R2 archive failed:", err);
        return new Response("R2 archive unavailable", { status: 502 });
      }

      // Mirror installation payloads into Analytics Engine for the fleet
      // dashboard. Non-blocking and best-effort: a WAE failure never changes
      // the response — R2 success is the contract.
      if (payload.type === "installation") {
        try {
          const d = payload.data;
          env.AE.writeDataPoint({
            indexes: [payload.instance_hash],
            blobs: [
              payload.instance_hash,
              d.profile,
              d.gateway_type,
              d.power_supply ?? "",
              d.integration_version ?? "",
              d.ha_version ?? "",
              d.climate_zone ?? "",
            ],
            doubles: [
              d.has_dhw ? 1 : 0,
              d.has_pool ? 1 : 0,
              d.has_cooling ? 1 : 0,
              d.has_secondary_compressor ? 1 : 0,
              d.max_circuits ?? 0,
              d.latitude ?? 0,
              d.longitude ?? 0,
            ],
          });
        } catch (err) {
          console.warn("WAE write failed:", err);
        }
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
