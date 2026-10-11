/**
 * Anonymous daily fleet ping (#468).
 *
 * One ping per Home Assistant instance and per UTC day, with no identifier:
 * counting the pings of a day gives the active installations of that day.
 * Validation is strict (unknown fields are rejected, every value is shape
 * checked) because nothing else bounds what an unauthenticated client sends,
 * and the request itself is never stored: only one Analytics Engine datapoint
 * per unit, built from the validated fields.
 */

import type { PingPayload, PingUnit } from "./types";
import { ValidationError } from "./validator";

/** A ping lists a handful of units; anything bigger is not a ping. */
export const MAX_PING_SIZE = 8 * 1024;
const MAX_UNITS = 16;

const VERSION_RE = /^[0-9A-Za-z.+-]{1,32}$/;
const KEY_RE = /^[a-z0-9_]{1,32}$/;
const KOPPEN_RE = /^[A-Z][A-Za-z]{0,2}$/;

const PING_FIELDS = new Set([
  "type",
  "integration_version",
  "ha_version",
  "climate_zone",
  "units",
]);
const UNIT_BOOLEANS = [
  "has_dhw",
  "has_pool",
  "has_cooling",
  "has_secondary_compressor",
] as const;
const UNIT_FIELDS = new Set([
  "profile",
  "gateway_type",
  "power_supply",
  "max_circuits",
  ...UNIT_BOOLEANS,
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rejectUnknown(obj: Record<string, unknown>, allowed: Set<string>, where: string): void {
  for (const key of Object.keys(obj)) {
    if (!allowed.has(key)) {
      throw new ValidationError(`${where}: unknown field "${key}"`);
    }
  }
}

function matching(value: unknown, re: RegExp, field: string): string {
  if (typeof value !== "string" || !re.test(value)) {
    throw new ValidationError(`ping: invalid ${field}`);
  }
  return value;
}

function validateUnit(raw: unknown, index: number): PingUnit {
  const where = `ping: units[${index}]`;
  if (!isObject(raw)) {
    throw new ValidationError(`${where} must be an object`);
  }
  rejectUnknown(raw, UNIT_FIELDS, where);

  if (raw.power_supply !== "single" && raw.power_supply !== "three") {
    throw new ValidationError(`${where}: invalid power_supply`);
  }
  const circuits = raw.max_circuits;
  if (typeof circuits !== "number" || !Number.isInteger(circuits) || circuits < 0 || circuits > 2) {
    throw new ValidationError(`${where}: invalid max_circuits`);
  }
  for (const flag of UNIT_BOOLEANS) {
    if (typeof raw[flag] !== "boolean") {
      throw new ValidationError(`${where}: ${flag} must be a boolean`);
    }
  }

  return {
    profile: matching(raw.profile, KEY_RE, `units[${index}].profile`),
    gateway_type: matching(raw.gateway_type, KEY_RE, `units[${index}].gateway_type`),
    power_supply: raw.power_supply,
    has_dhw: raw.has_dhw as boolean,
    has_pool: raw.has_pool as boolean,
    has_cooling: raw.has_cooling as boolean,
    max_circuits: circuits,
    has_secondary_compressor: raw.has_secondary_compressor as boolean,
  };
}

/** Validate a fleet ping body. Throws ValidationError on any deviation. */
export function validatePing(raw: string): PingPayload {
  if (raw.length > MAX_PING_SIZE) {
    throw new ValidationError("Payload too large", 413);
  }
  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch {
    throw new ValidationError("Invalid JSON");
  }
  if (!isObject(payload)) {
    throw new ValidationError("Payload must be a JSON object");
  }
  rejectUnknown(payload, PING_FIELDS, "ping");
  if (payload.type !== "ping") {
    throw new ValidationError('ping: "type" must be "ping"');
  }

  const zone = payload.climate_zone;
  if (zone != null && (typeof zone !== "string" || !KOPPEN_RE.test(zone))) {
    throw new ValidationError("ping: invalid climate_zone");
  }

  const units = payload.units;
  if (!Array.isArray(units) || units.length === 0 || units.length > MAX_UNITS) {
    throw new ValidationError(`ping: units must hold 1 to ${MAX_UNITS} entries`);
  }

  return {
    type: "ping",
    integration_version: matching(payload.integration_version, VERSION_RE, "integration_version"),
    ha_version: matching(payload.ha_version, VERSION_RE, "ha_version"),
    climate_zone: (zone as string | null | undefined) ?? null,
    units: units.map(validateUnit),
  };
}

/**
 * Write one datapoint per unit.
 *
 * Instance-level fields are repeated on every unit; double1 is 1 on the first
 * unit only, so SUM(double1) counts installations and COUNT counts units.
 * No index: there is no identity to sample on, by design.
 *
 *   blob1 integration_version  blob2 ha_version  blob3 climate_zone
 *   blob4 profile  blob5 gateway_type  blob6 power_supply
 *   double1 installation weight  double2 has_dhw  double3 has_pool
 *   double4 has_cooling  double5 max_circuits  double6 has_secondary_compressor
 */
export function writePing(dataset: AnalyticsEngineDataset, ping: PingPayload): void {
  ping.units.forEach((unit, i) => {
    dataset.writeDataPoint({
      blobs: [
        ping.integration_version,
        ping.ha_version,
        ping.climate_zone ?? "",
        unit.profile,
        unit.gateway_type,
        unit.power_supply,
      ],
      doubles: [
        i === 0 ? 1 : 0,
        unit.has_dhw ? 1 : 0,
        unit.has_pool ? 1 : 0,
        unit.has_cooling ? 1 : 0,
        unit.max_circuits,
        unit.has_secondary_compressor ? 1 : 0,
      ],
    });
  });
}
