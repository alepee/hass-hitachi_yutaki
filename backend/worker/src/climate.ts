/**
 * Köppen-Geiger climate zone lookup from rounded coordinates.
 * Data source: Beck et al. (2018), via kgcpy, 1° resolution.
 */

import lookup from "./koppen-lookup.json";

const KOPPEN_LOOKUP = lookup as Record<string, string>;

/**
 * Look up the Köppen-Geiger climate zone for given coordinates.
 * Coordinates should already be rounded to 1° integers.
 * Returns null if no land classification exists at that point.
 */
export function classifyClimateZone(
  latitude: number | null | undefined,
  longitude: number | null | undefined,
): string | null {
  if (latitude == null || longitude == null) {
    return null;
  }
  const lat = Math.round(latitude);
  const lon = Math.round(longitude);
  return KOPPEN_LOOKUP[`${lat},${lon}`] ?? null;
}
