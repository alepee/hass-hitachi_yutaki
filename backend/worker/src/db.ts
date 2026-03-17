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
      has_secondary_compressor, first_seen, last_seen
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW(),NOW())
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
    ],
  );
}

/** Insert a batch of metric points. */
export async function writeMetrics(
  client: Client,
  payload: MetricsPayload,
): Promise<void> {
  // Build multi-row INSERT for efficiency
  const cols = [
    "time",
    "instance_hash",
    "outdoor_temp",
    "water_inlet_temp",
    "water_outlet_temp",
    "dhw_temp",
    "compressor_on",
    "compressor_frequency",
    "compressor_current",
    "thermal_power",
    "electrical_power",
    "cop_instant",
    "cop_quality",
    "unit_mode",
    "is_defrosting",
    "dhw_active",
    "circuit1_water_temp",
    "circuit2_water_temp",
    "circuit1_target_temp",
    "circuit2_target_temp",
    "dhw_target_temp",
    "water_target_temp",
    "water_flow",
    "circuit1_otc_method_heating",
    "circuit1_otc_method_cooling",
    "circuit1_eco_mode",
    "circuit2_eco_mode",
    "circuit1_power",
    "circuit2_power",
    "dhw_power",
  ];

  const values: unknown[] = [];
  const placeholders: string[] = [];

  for (let i = 0; i < payload.points.length; i++) {
    const p = payload.points[i];
    const offset = i * cols.length;
    const row = cols.map((_, j) => `$${offset + j + 1}`);
    placeholders.push(`(${row.join(",")})`);
    values.push(
      p.time,
      payload.instance_hash,
      p.outdoor_temp ?? null,
      p.water_inlet_temp ?? null,
      p.water_outlet_temp ?? null,
      p.dhw_temp ?? null,
      p.compressor_on ?? null,
      p.compressor_frequency ?? null,
      p.compressor_current ?? null,
      p.thermal_power ?? null,
      p.electrical_power ?? null,
      p.cop_instant ?? null,
      p.cop_quality ?? null,
      p.unit_mode ?? null,
      p.is_defrosting ?? null,
      p.dhw_active ?? null,
      p.circuit1_water_temp ?? null,
      p.circuit2_water_temp ?? null,
      p.circuit1_target_temp ?? null,
      p.circuit2_target_temp ?? null,
      p.dhw_target_temp ?? null,
      p.water_target_temp ?? null,
      p.water_flow ?? null,
      p.circuit1_otc_method_heating ?? null,
      p.circuit1_otc_method_cooling ?? null,
      p.circuit1_eco_mode ?? null,
      p.circuit2_eco_mode ?? null,
      p.circuit1_power ?? null,
      p.circuit2_power ?? null,
      p.dhw_power ?? null,
    );
  }

  await client.query(
    `INSERT INTO metrics (${cols.join(",")}) VALUES ${placeholders.join(",")}`,
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
