# Telemetry Backend

Anonymous telemetry ingestion pipeline for the Hitachi Yutaki integration.

## Architecture

```
HA Integration (HttpTelemetryClient)
    → POST /v1/ingest (gzip JSON)
    → Cloudflare Worker (validate, rate limit, enrich with Köppen zone)
        → R2 (permanent JSON archive, partitioned Hive-style)
```

## Infrastructure

| Service | Identifier | Purpose |
|---------|------------|---------|
| **Cloudflare Worker** | `hitachi-telemetry.antoine-04c.workers.dev` | Ingestion proxy |
| **R2** | `hitachi-telemetry-archive` | Permanent JSON archive of all payloads |

## Querying the archive

R2 holds every telemetry payload as JSON, partitioned Hive-style by date. The recommended way to explore the archive is DuckDB with the `httpfs` extension and an R2 access key:

```sql
INSTALL httpfs; LOAD httpfs;
SET s3_endpoint = '<account-id>.r2.cloudflarestorage.com';
SET s3_access_key_id = '<r2-access-key>';
SET s3_secret_access_key = '<r2-secret>';

SELECT instance_hash, COUNT(*) AS points
FROM read_json_auto(
  's3://hitachi-telemetry-archive/metrics/year=2026/month=04/day=*/batch_*.json'
)
GROUP BY 1
ORDER BY points DESC;
```

## Worker

### Local development

```bash
cd backend/worker
npm install
npx wrangler dev    # Runs locally with bindings
```

### Deploy

```bash
cd backend/worker
npx wrangler login  # One-time OAuth (opens browser)
npx wrangler deploy
```

### TypeScript structure

```
src/
├── index.ts          — Entry point, routing, gzip decompression
├── types.ts          — Payload type definitions
├── validator.ts      — JSON validation + field whitelist (final anonymization)
├── rate-limiter.ts   — Per-hash rate limiting via Cache API (1 req/min)
├── archive.ts        — R2 writes (Hive-style partitioned JSON)
├── climate.ts        — Köppen-Geiger lookup from rounded coordinates
└── koppen-lookup.json — 14,938-entry climate zone table (Beck et al. 2018)
```

### Endpoint

`POST /v1/ingest`

- **Content-Type**: `application/json`
- **Content-Encoding**: `gzip` (optional)
- **X-Instance-Hash**: SHA-256 hex (must match payload)

**Payload types**: `installation`, `metrics`, `daily_stats`, `snapshot`

**Responses**: `202` Accepted, `400` Bad Request, `413` Too Large, `429` Rate Limited, `500` Error, `502` R2 Unavailable

### Köppen enrichment

The Worker enriches `installation` payloads with a precise Köppen-Geiger climate zone (e.g., `Cfb`, `Csa`, `Dfb`) using a server-side lookup table. The client sends coordinates rounded to 1° (~110 km), the Worker classifies.

## Provisioning from scratch

If you need to recreate the infrastructure:

### 1. Cloudflare resources

```bash
# R2 bucket for the archive
npx wrangler r2 bucket create hitachi-telemetry-archive
```

Or use Cloudflare MCP tools (`accounts_list`, `r2_bucket_create`).

### 2. Deploy Worker

```bash
cd backend/worker
npm install
npx wrangler login
npx wrangler deploy
```
