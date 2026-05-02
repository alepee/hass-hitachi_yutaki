/** Cloudflare Worker environment bindings. */
export interface Env {
  ARCHIVE: R2Bucket;
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
    latitude?: number | null;
    longitude?: number | null;
    climate_zone?: string | null;
  };
}

/** Single metric data point — dynamic keys from integration data keys. */
export interface MetricPoint {
  time: string;
  [key: string]: unknown;
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
