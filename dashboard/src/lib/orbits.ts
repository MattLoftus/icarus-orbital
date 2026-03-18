/**
 * Client-side circular orbit computation for planet positions.
 * Mirrors the Python reference_missions.py approach — same constants.
 * Used to animate planet positions during trajectory playback without API calls.
 */

const AU_KM = 1.495978707e8;

// Circular orbit parameters: semi-major axis (AU), period (days), J2000 mean longitude (deg)
const PLANET_ORBITS: Record<string, { a_au: number; period_days: number; lon_j2000: number }> = {
  mercury: { a_au: 0.387, period_days: 87.97,   lon_j2000: 252.25 },
  venus:   { a_au: 0.723, period_days: 224.7,    lon_j2000: 181.98 },
  earth:   { a_au: 1.000, period_days: 365.25,   lon_j2000: 100.46 },
  mars:    { a_au: 1.524, period_days: 686.97,   lon_j2000: 355.45 },
  jupiter: { a_au: 5.203, period_days: 4332.6,   lon_j2000: 34.40 },
  saturn:  { a_au: 9.537, period_days: 10759.2,  lon_j2000: 49.94 },
  uranus:  { a_au: 19.19, period_days: 30687.0,  lon_j2000: 313.23 },
  neptune: { a_au: 30.07, period_days: 60190.0,  lon_j2000: 304.88 },
};

// J2000 epoch: 2000-01-01T12:00:00 UTC
const J2000_MS = Date.UTC(2000, 0, 1, 12, 0, 0);

/**
 * Compute approximate heliocentric position [x, y, z] in km for a planet
 * at a given date string (e.g. "2026-03-15"). Uses circular orbit in ecliptic plane.
 */
export function planetPositionAtDate(
  body: string,
  dateStr: string
): [number, number, number] {
  const orb = PLANET_ORBITS[body.toLowerCase()];
  if (!orb) return [0, 0, 0];

  const dateMs = new Date(dateStr + 'T12:00:00Z').getTime();
  const dtDays = (dateMs - J2000_MS) / 86400000;

  const meanLonRad = (orb.lon_j2000 * Math.PI / 180) + (2 * Math.PI * dtDays / orb.period_days);
  const rKm = orb.a_au * AU_KM;

  return [
    rKm * Math.cos(meanLonRad),
    rKm * Math.sin(meanLonRad),
    0,
  ];
}

/**
 * Compute planet positions for all planets at a given date.
 * Returns same format as the API PlanetState but computed client-side.
 */
export function allPlanetPositionsAtDate(dateStr: string): Record<string, [number, number, number]> {
  const result: Record<string, [number, number, number]> = {};
  for (const body of Object.keys(PLANET_ORBITS)) {
    result[body] = planetPositionAtDate(body, dateStr);
  }
  return result;
}

/**
 * Interpolate a date between two date strings based on progress (0-1).
 */
export function interpolateDate(startDate: string, endDate: string, progress: number): string {
  const startMs = new Date(startDate + 'T12:00:00Z').getTime();
  const endMs = new Date(endDate + 'T12:00:00Z').getTime();
  const currentMs = startMs + progress * (endMs - startMs);
  return new Date(currentMs).toISOString().slice(0, 10);
}
