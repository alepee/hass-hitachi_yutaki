/** Cloudflare Worker environment bindings. */
export interface Env {
  DB: Hyperdrive;
  ARCHIVE: R2Bucket;
  RATE_LIMIT: KVNamespace;
}

/** Base payload with type discriminator. */
export interface BasePayload {
  type: string;
  instance_hash: string;
}

/** Installation info payload. */
export interface InstallationPayload extends BasePayload {
  type: "installation";
  data: {
    profile: string;
    gateway_type: string;
    ha_version?: string;
    integration_version?: string;
    power_supply?: string;
    has_dhw?: boolean;
    has_pool?: boolean;
    has_cooling?: boolean;
    max_circuits?: number;
    has_secondary_compressor?: boolean;
  };
}

/** Single metric data point. */
export interface MetricPoint {
  time: string;
  outdoor_temp?: number | null;
  water_inlet_temp?: number | null;
  water_outlet_temp?: number | null;
  dhw_temp?: number | null;
  compressor_on?: boolean | null;
  compressor_frequency?: number | null;
  compressor_current?: number | null;
  thermal_power?: number | null;
  electrical_power?: number | null;
  cop_instant?: number | null;
  cop_quality?: string | null;
  unit_mode?: string | null;
  is_defrosting?: boolean | null;
  dhw_active?: boolean | null;
  circuit1_water_temp?: number | null;
  circuit2_water_temp?: number | null;
  circuit1_target_temp?: number | null;
  circuit2_target_temp?: number | null;
  dhw_target_temp?: number | null;
  water_target_temp?: number | null;
  water_flow?: number | null;
  circuit1_otc_method_heating?: string | null;
  circuit1_otc_method_cooling?: string | null;
  circuit1_eco_mode?: boolean | null;
  circuit2_eco_mode?: boolean | null;
  circuit1_power?: boolean | null;
  circuit2_power?: boolean | null;
  dhw_power?: boolean | null;
}

/** Metrics batch payload. */
export interface MetricsPayload extends BasePayload {
  type: "metrics";
  points: MetricPoint[];
}

/** Daily stats payload. */
export interface DailyStatsPayload extends BasePayload {
  type: "daily_stats";
  date: string;
  data: {
    outdoor_temp_min?: number | null;
    outdoor_temp_max?: number | null;
    outdoor_temp_avg?: number | null;
    cop_avg?: number | null;
    cop_min?: number | null;
    cop_max?: number | null;
    cop_quality_best?: string | null;
    compressor_starts?: number;
    compressor_hours?: number;
    defrost_count?: number;
    defrost_total_minutes?: number;
    thermal_energy_kwh?: number;
    electrical_energy_kwh?: number;
    heating_hours?: number;
    cooling_hours?: number;
    dhw_hours?: number;
  };
}

/** Register snapshot payload. */
export interface SnapshotPayload extends BasePayload {
  type: "snapshot";
  profile: string;
  gateway_type: string;
  registers: Record<string, number>;
}

export type TelemetryPayload =
  | InstallationPayload
  | MetricsPayload
  | DailyStatsPayload
  | SnapshotPayload;
