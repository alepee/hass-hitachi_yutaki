# Telemetry Backend

Anonymous telemetry ingestion pipeline for the Hitachi Yutaki integration.

## Architecture

```
HA Integration (HttpTelemetryClient)
    → POST /v1/ingest (gzip JSON)
    → Cloudflare Worker (validate, rate limit, enrich with Köppen zone)
        → TigerData (hot, 30-day rolling, TimescaleDB)
        → R2 (cold, permanent JSON archive)
    → Grafana Cloud (dashboards)
```

## Infrastructure

| Service | ID / URL | Purpose |
|---------|----------|---------|
| **TigerData** | `ojqwsu3e4j` (us-east-1) | TimescaleDB — hot storage |
| **Cloudflare Worker** | `hitachi-telemetry.antoine-04c.workers.dev` | Ingestion proxy |
| **Hyperdrive** | `6022ba5b4aa84149bced9823002142d7` | Connection pooling Worker → TigerData |
| **R2 Bucket** | `hitachi-telemetry-archive` | Cold JSON archive |
| **Grafana Cloud** | `alepee.grafana.net` | Dashboards (datasource: `TigerData`) |

## Database

### Roles

| Role | Purpose | Permissions |
|------|---------|-------------|
| `tsdbadmin` | Admin (provisioning) | Full |
| `worker_write` | Worker ingestion | INSERT + UPDATE on all tables |
| `grafana_read` | Grafana dashboards | SELECT on all tables + views |

### Tables

- **`installations`** — one row per instance (upserted daily)
- **`metrics`** — hypertable, fine metrics every 5min (ON level), 30-day retention
- **`daily_stats`** — daily aggregates, kept indefinitely
- **`register_snapshots`** — hypertable, Modbus register dumps, 90-day retention
- **`metrics_daily_agg`** — continuous aggregate (auto-downsampled from metrics)

### Migrations

Run with `tiger db connect < backend/migrations/NNN_*.sql` or via MCP:

```
001_initial_schema.sql           — tables, hypertables, indexes
002_compression_retention.sql    — compression, retention, continuous aggregate
003_roles.sql                    — worker_write + grafana_read roles
004_world_model_fields.sql       — setpoints, flow, OTC, control state
005_extended_world_model_fields.sql — compressor thermo, secondary, system state
006_geolocation.sql              — latitude, longitude, climate_zone
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
├── db.ts             — TigerData writes (parameterized INSERT via Hyperdrive)
├── archive.ts        — R2 cold writes (Hive-style partitioned JSON)
├── climate.ts        — Köppen-Geiger lookup from rounded coordinates
└── koppen-lookup.json — 14,938-entry climate zone table (Beck et al. 2018)
```

### Endpoint

`POST /v1/ingest`

- **Content-Type**: `application/json`
- **Content-Encoding**: `gzip` (optional)
- **X-Instance-Hash**: SHA-256 hex (must match payload)

**Payload types**: `installation`, `metrics`, `daily_stats`, `snapshot`

**Responses**: `202` Accepted, `400` Bad Request, `413` Too Large, `429` Rate Limited, `500` Error

### Köppen enrichment

The Worker enriches `installation` payloads with a precise Köppen-Geiger climate zone (e.g., `Cfb`, `Csa`, `Dfb`) using a server-side lookup table. The client sends coordinates rounded to 1° (~110 km), the Worker classifies.

## Grafana Dashboards

Import via **Dashboards → Import → Upload JSON**:

| Dashboard | File | Content |
|-----------|------|---------|
| Fleet Overview | `grafana/fleet-overview.json` | Active installations, model/version distribution |
| Performance | `grafana/performance.json` | COP, temperatures, compressor, power (with instance filter) |
| Snapshots | `grafana/snapshots.json` | Browse register snapshots by model |

Datasource must be named `TigerData` (PostgreSQL pointing to TigerData with `grafana_read` role).

## Provisioning from scratch

If you need to recreate the infrastructure:

### 1. TigerData

```bash
tiger service create --name hitachi-telemetry  # us-east-1 (free tier)
# Apply migrations in order:
tiger db connect < backend/migrations/001_initial_schema.sql
tiger db connect < backend/migrations/002_compression_retention.sql
tiger db connect < backend/migrations/003_roles.sql  # Change passwords first!
tiger db connect < backend/migrations/004_world_model_fields.sql
tiger db connect < backend/migrations/005_extended_world_model_fields.sql
tiger db connect < backend/migrations/006_geolocation.sql
```

### 2. Cloudflare resources

```bash
# R2 bucket for cold archive
npx wrangler r2 bucket create hitachi-telemetry-archive

# Hyperdrive for connection pooling
npx wrangler hyperdrive create hitachi-telemetry \
  --connection-string="postgresql://worker_write:<PASSWORD>@<HOST>:<PORT>/tsdb?sslmode=require"
# → update id in wrangler.toml
```

Or use Cloudflare MCP tools (`accounts_list`, `r2_bucket_create`, and `cloudflare-api execute` for Hyperdrive).

### 3. Deploy Worker

```bash
cd backend/worker
npm install
npx wrangler login
npx wrangler deploy
```

### 4. Grafana

Add PostgreSQL datasource pointing to TigerData with `grafana_read` role, then import the 3 dashboard JSONs.
