/**
 * JSON schema validation for telemetry payloads.
 * Validates structure and strips unknown fields (final anonymization).
 */

import type {
  DailyStatsPayload,
  InstallationPayload,
  MetricPoint,
  MetricsPayload,
  SnapshotPayload,
  TelemetryPayload,
} from "./types";

const INSTANCE_HASH_RE = /^[a-f0-9]{64}$/;
const MAX_PAYLOAD_SIZE = 50 * 1024; // 50 KB uncompressed
const MAX_METRICS_POINTS = 500;

/** Allowed installation data fields (whitelist). */
const INSTALLATION_FIELDS = new Set([
  "profile",
  "gateway_type",
  "ha_version",
  "integration_version",
  "power_supply",
  "has_dhw",
  "has_pool",
  "has_cooling",
  "max_circuits",
  "has_secondary_compressor",
]);

/** Allowed metric point fields (whitelist). */
const METRIC_FIELDS = new Set([
  "time",
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
  "circuit2_otc_method_heating",
  "circuit2_otc_method_cooling",
  "circuit1_eco_mode",
  "circuit2_eco_mode",
  "circuit1_power",
  "circuit2_power",
  "dhw_power",
  "circuit1_max_flow_temp_heating",
  "circuit1_max_flow_temp_cooling",
  "circuit1_heat_eco_offset",
  "circuit1_cool_eco_offset",
  "circuit2_max_flow_temp_heating",
  "circuit2_max_flow_temp_cooling",
  "circuit2_heat_eco_offset",
  "circuit2_cool_eco_offset",
  "compressor_tg_gas_temp",
  "compressor_ti_liquid_temp",
  "compressor_td_discharge_temp",
  "compressor_te_evaporator_temp",
  "compressor_evi_valve_opening",
  "compressor_evo_valve_opening",
  "secondary_compressor_frequency",
  "secondary_compressor_discharge_temp",
  "secondary_compressor_suction_temp",
  "secondary_compressor_discharge_pressure",
  "secondary_compressor_suction_pressure",
  "secondary_compressor_valve_opening",
  "unit_power",
  "pump_speed",
  "operation_state_code",
  "alarm_code",
  "system_status",
  "dhw_boost",
  "dhw_high_demand",
  "water_outlet_2_temp",
  "water_outlet_3_temp",
  "pool_current_temp",
  "pool_target_temp",
]);

/** Allowed daily stats data fields (whitelist). */
const DAILY_STATS_FIELDS = new Set([
  "outdoor_temp_min",
  "outdoor_temp_max",
  "outdoor_temp_avg",
  "cop_avg",
  "cop_min",
  "cop_max",
  "cop_quality_best",
  "compressor_starts",
  "compressor_hours",
  "defrost_count",
  "defrost_total_minutes",
  "thermal_energy_kwh",
  "electrical_energy_kwh",
  "heating_hours",
  "cooling_hours",
  "dhw_hours",
]);

export class ValidationError extends Error {
  constructor(
    message: string,
    public statusCode: number = 400,
  ) {
    super(message);
  }
}

/** Strip object to only whitelisted keys. */
function whitelist(
  obj: Record<string, unknown>,
  allowed: Set<string>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const key of allowed) {
    if (key in obj) {
      result[key] = obj[key];
    }
  }
  return result;
}

/** Validate and sanitize a telemetry payload. */
export function validate(
  raw: string,
  instanceHashHeader: string | null,
): TelemetryPayload {
  if (raw.length > MAX_PAYLOAD_SIZE) {
    throw new ValidationError("Payload too large", 413);
  }

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(raw);
  } catch {
    throw new ValidationError("Invalid JSON");
  }

  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    throw new ValidationError("Payload must be a JSON object");
  }

  // Validate instance_hash
  const instanceHash = String(payload.instance_hash ?? "");
  if (!INSTANCE_HASH_RE.test(instanceHash)) {
    throw new ValidationError("Invalid instance_hash (expected SHA-256 hex)");
  }

  // Cross-check with header
  if (instanceHashHeader && instanceHashHeader !== instanceHash) {
    throw new ValidationError("instance_hash mismatch with X-Instance-Hash header");
  }

  const type = payload.type;
  if (typeof type !== "string") {
    throw new ValidationError('Missing or invalid "type" field');
  }

  switch (type) {
    case "installation":
      return validateInstallation(payload, instanceHash);
    case "metrics":
      return validateMetrics(payload, instanceHash);
    case "daily_stats":
      return validateDailyStats(payload, instanceHash);
    case "snapshot":
      return validateSnapshot(payload, instanceHash);
    default:
      throw new ValidationError(`Unknown payload type: ${type}`);
  }
}

function validateInstallation(
  payload: Record<string, unknown>,
  instanceHash: string,
): InstallationPayload {
  const data = payload.data;
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new ValidationError("installation: missing data object");
  }
  const d = data as Record<string, unknown>;
  if (typeof d.profile !== "string" || typeof d.gateway_type !== "string") {
    throw new ValidationError("installation: profile and gateway_type are required strings");
  }
  return {
    type: "installation",
    instance_hash: instanceHash,
    data: whitelist(d, INSTALLATION_FIELDS) as InstallationPayload["data"],
  };
}

function validateMetrics(
  payload: Record<string, unknown>,
  instanceHash: string,
): MetricsPayload {
  const points = payload.points;
  if (!Array.isArray(points) || points.length === 0) {
    throw new ValidationError("metrics: points must be a non-empty array");
  }
  if (points.length > MAX_METRICS_POINTS) {
    throw new ValidationError(`metrics: too many points (max ${MAX_METRICS_POINTS})`);
  }
  const sanitized: MetricPoint[] = points.map((p: unknown, i: number) => {
    if (typeof p !== "object" || p === null) {
      throw new ValidationError(`metrics: point[${i}] must be an object`);
    }
    const point = p as Record<string, unknown>;
    if (typeof point.time !== "string") {
      throw new ValidationError(`metrics: point[${i}].time is required`);
    }
    return whitelist(point, METRIC_FIELDS) as unknown as MetricPoint;
  });
  return {
    type: "metrics",
    instance_hash: instanceHash,
    points: sanitized,
  };
}

function validateDailyStats(
  payload: Record<string, unknown>,
  instanceHash: string,
): DailyStatsPayload {
  if (typeof payload.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(payload.date)) {
    throw new ValidationError("daily_stats: date must be YYYY-MM-DD");
  }
  const data = payload.data;
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new ValidationError("daily_stats: missing data object");
  }
  return {
    type: "daily_stats",
    instance_hash: instanceHash,
    date: payload.date,
    data: whitelist(data as Record<string, unknown>, DAILY_STATS_FIELDS) as DailyStatsPayload["data"],
  };
}

function validateSnapshot(
  payload: Record<string, unknown>,
  instanceHash: string,
): SnapshotPayload {
  if (typeof payload.profile !== "string" || typeof payload.gateway_type !== "string") {
    throw new ValidationError("snapshot: profile and gateway_type are required");
  }
  const registers = payload.registers;
  if (typeof registers !== "object" || registers === null || Array.isArray(registers)) {
    throw new ValidationError("snapshot: registers must be an object");
  }
  // Whitelist: only string keys with numeric values
  const sanitized: Record<string, number> = {};
  for (const [key, value] of Object.entries(registers as Record<string, unknown>)) {
    if (typeof value === "number" && isFinite(value)) {
      sanitized[key] = value;
    }
  }
  return {
    type: "snapshot",
    instance_hash: instanceHash,
    profile: payload.profile as string,
    gateway_type: payload.gateway_type as string,
    registers: sanitized,
  };
}
