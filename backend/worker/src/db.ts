/**
 * TigerData (TimescaleDB) write operations.
 * Uses Hyperdrive for connection pooling.
 */

import { Client } from "pg";
import type {
  DailyStatsPayload,
  InstallationPayload,
  MetricsPayload,
  SnapshotPayload,
} from "./types";

/** Create a pg Client using Hyperdrive connection string. */
export async function getClient(connectionString: string): Promise<Client> {
  const client = new Client({ connectionString });
  await client.connect();
  return client;
}

/** Upsert installation info. */
export async function writeInstallation(
  client: Client,
  payload: InstallationPayload,
): Promise<void> {
  const d = payload.data;
  await client.query(
    `INSERT INTO installations (
      instance_hash, profile, gateway_type, ha_version, integration_version,
      power_supply, has_dhw, has_pool, has_cooling, max_circuits,
      has_secondary_compressor, latitude, longitude, climate_zone,
      first_seen, last_seen
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,NOW(),NOW())
    ON CONFLICT (instance_hash) DO UPDATE SET
      profile = EXCLUDED.profile,
      gateway_type = EXCLUDED.gateway_type,
      ha_version = EXCLUDED.ha_version,
      integration_version = EXCLUDED.integration_version,
      power_supply = EXCLUDED.power_supply,
      has_dhw = EXCLUDED.has_dhw,
      has_pool = EXCLUDED.has_pool,
      has_cooling = EXCLUDED.has_cooling,
      max_circuits = EXCLUDED.max_circuits,
      has_secondary_compressor = EXCLUDED.has_secondary_compressor,
      latitude = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      climate_zone = EXCLUDED.climate_zone,
      last_seen = NOW()`,
    [
      payload.instance_hash,
      d.profile,
      d.gateway_type,
      d.ha_version ?? null,
      d.integration_version ?? null,
      d.power_supply ?? null,
      d.has_dhw ?? null,
      d.has_pool ?? null,
      d.has_cooling ?? null,
      d.max_circuits ?? null,
      d.has_secondary_compressor ?? null,
      d.latitude ?? null,
      d.longitude ?? null,
      d.climate_zone ?? null,
    ],
  );
}

/** Insert a batch of metric points using JSONB storage. */
export async function writeMetrics(
  client: Client,
  payload: MetricsPayload,
): Promise<void> {
  const values: unknown[] = [];
  const placeholders: string[] = [];

  for (let i = 0; i < payload.points.length; i++) {
    const p = payload.points[i];
    const offset = i * 3;
    placeholders.push(`($${offset + 1}, $${offset + 2}, $${offset + 3})`);
    values.push(
      p.time,
      payload.instance_hash,
      JSON.stringify(p),
    );
  }

  await client.query(
    `INSERT INTO metrics (time, instance_hash, data) VALUES ${placeholders.join(",")}`,
    values,
  );
}

/** Insert daily stats (upsert on date + instance_hash). */
export async function writeDailyStats(
  client: Client,
  payload: DailyStatsPayload,
): Promise<void> {
  const d = payload.data;
  await client.query(
    `INSERT INTO daily_stats (
      date, instance_hash,
      outdoor_temp_min, outdoor_temp_max, outdoor_temp_avg,
      cop_avg, cop_min, cop_max, cop_quality_best,
      compressor_starts, compressor_hours,
      defrost_count, defrost_total_minutes,
      thermal_energy_kwh, electrical_energy_kwh,
      heating_hours, cooling_hours, dhw_hours
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
    ON CONFLICT (date, instance_hash) DO UPDATE SET
      outdoor_temp_min = EXCLUDED.outdoor_temp_min,
      outdoor_temp_max = EXCLUDED.outdoor_temp_max,
      outdoor_temp_avg = EXCLUDED.outdoor_temp_avg,
      cop_avg = EXCLUDED.cop_avg,
      cop_min = EXCLUDED.cop_min,
      cop_max = EXCLUDED.cop_max,
      cop_quality_best = EXCLUDED.cop_quality_best,
      compressor_starts = EXCLUDED.compressor_starts,
      compressor_hours = EXCLUDED.compressor_hours,
      defrost_count = EXCLUDED.defrost_count,
      defrost_total_minutes = EXCLUDED.defrost_total_minutes,
      thermal_energy_kwh = EXCLUDED.thermal_energy_kwh,
      electrical_energy_kwh = EXCLUDED.electrical_energy_kwh,
      heating_hours = EXCLUDED.heating_hours,
      cooling_hours = EXCLUDED.cooling_hours,
      dhw_hours = EXCLUDED.dhw_hours`,
    [
      payload.date,
      payload.instance_hash,
      d.outdoor_temp_min ?? null,
      d.outdoor_temp_max ?? null,
      d.outdoor_temp_avg ?? null,
      d.cop_avg ?? null,
      d.cop_min ?? null,
      d.cop_max ?? null,
      d.cop_quality_best ?? null,
      d.compressor_starts ?? 0,
      d.compressor_hours ?? 0,
      d.defrost_count ?? 0,
      d.defrost_total_minutes ?? 0,
      d.thermal_energy_kwh ?? 0,
      d.electrical_energy_kwh ?? 0,
      d.heating_hours ?? 0,
      d.cooling_hours ?? 0,
      d.dhw_hours ?? 0,
    ],
  );
}

/** Insert a register snapshot. */
export async function writeSnapshot(
  client: Client,
  payload: SnapshotPayload,
): Promise<void> {
  await client.query(
    `INSERT INTO register_snapshots (time, instance_hash, profile, gateway_type, registers)
     VALUES (NOW(), $1, $2, $3, $4)`,
    [
      payload.instance_hash,
      payload.profile,
      payload.gateway_type,
      JSON.stringify(payload.registers),
    ],
  );
}
