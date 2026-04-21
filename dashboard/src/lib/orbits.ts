/**
 * Client-side Keplerian orbit computation for planet positions.
 * Used to animate planets during trajectory playback without API calls.
 *
 * Uses standard J2000 mean orbital elements (Standish 1992). For 1800-2050
 * the RMS error vs SPICE DE440s is under ~0.1° — visually indistinguishable
 * from the SPICE orbit traces drawn in the scene.
 *
 * This replaces an earlier circular/ecliptic approximation that caused
 * outer planets to drift off their orbit-trace lines over multi-year
 * missions like Voyager 2.
 */

const AU_KM = 1.495978707e8;
const DEG = Math.PI / 180;

interface Elements {
  a: number;         // semi-major axis (AU)
  e: number;         // eccentricity
  i: number;         // inclination (rad)
  om: number;        // longitude of ascending node (rad)
  w: number;         // argument of periapsis (rad)
  m0: number;        // mean anomaly at J2000 (rad)
  period_days: number;
}

// J2000 heliocentric ecliptic elements (Standish 1992). Angles originally in
// degrees; converted to radians here. Values are ϖ = Ω + ω and L = M + ϖ from
// the reference, so w = ϖ - Ω and m0 = L - ϖ at J2000.
const ELEMENTS: Record<string, Elements> = {
  mercury: {
    a: 0.38709927, e: 0.20563593,
    i:  7.00497902 * DEG,
    om: 48.33076593 * DEG,
    w:  (77.45779628 -  48.33076593) * DEG,
    m0: (252.25032350 - 77.45779628) * DEG,
    period_days: 87.969,
  },
  venus: {
    a: 0.72333566, e: 0.00677672,
    i:  3.39467605 * DEG,
    om: 76.67984255 * DEG,
    w:  (131.60246718 - 76.67984255) * DEG,
    m0: (181.97909950 - 131.60246718) * DEG,
    period_days: 224.701,
  },
  earth: {
    a: 1.00000261, e: 0.01671123,
    i:  -0.00001531 * DEG,
    om: 0,
    w:  102.93768193 * DEG,
    m0: (100.46457166 - 102.93768193) * DEG,
    period_days: 365.256,
  },
  mars: {
    a: 1.52371034, e: 0.09339410,
    i:  1.84969142 * DEG,
    om: 49.55953891 * DEG,
    w:  ((336.05637000) - 49.55953891) * DEG,  // ϖ = -23.94363 + 360
    m0: ((-4.55343205) - (-23.94362959)) * DEG,
    period_days: 686.980,
  },
  jupiter: {
    a: 5.20288700, e: 0.04838624,
    i:  1.30439695 * DEG,
    om: 100.47390909 * DEG,
    w:  (14.72847983 - 100.47390909 + 360) * DEG,
    m0: (34.39644051 -  14.72847983) * DEG,
    period_days: 4332.589,
  },
  saturn: {
    a: 9.53667594, e: 0.05386179,
    i:  2.48599187 * DEG,
    om: 113.66242448 * DEG,
    w:  (92.59887831 - 113.66242448 + 360) * DEG,
    m0: (49.95424423 -  92.59887831 + 360) * DEG,
    period_days: 10759.22,
  },
  uranus: {
    a: 19.18916464, e: 0.04725744,
    i:  0.77263783 * DEG,
    om: 74.01692503 * DEG,
    w:  (170.95427630 - 74.01692503) * DEG,
    m0: (313.23810451 - 170.95427630) * DEG,
    period_days: 30685.4,
  },
  neptune: {
    a: 30.06992276, e: 0.00859048,
    i:  1.77004347 * DEG,
    om: 131.78422574 * DEG,
    w:  (44.96476227 - 131.78422574 + 360) * DEG,
    m0: (-55.12002969 - 44.96476227 + 360) * DEG,
    period_days: 60189.0,
  },
  pluto: {
    a: 39.48168677, e: 0.24880766,
    i:  17.14175 * DEG,
    om: 110.30347 * DEG,
    w:  113.76329 * DEG,
    m0: 14.86228 * DEG,
    period_days: 90560.0,
  },
};

const J2000_MS = Date.UTC(2000, 0, 1, 12, 0, 0);

function solveKepler(M: number, e: number): number {
  // Newton's method for E - e*sin(E) = M
  let E = M + e * Math.sin(M);
  for (let k = 0; k < 50; k++) {
    const f  = E - e * Math.sin(E) - M;
    const fp = 1 - e * Math.cos(E);
    const dE = f / fp;
    E -= dE;
    if (Math.abs(dE) < 1e-12) break;
  }
  return E;
}

/**
 * Heliocentric position [x, y, z] in km in the J2000 ecliptic frame
 * for a planet at a UTC date string (e.g. "2026-03-15").
 */
export function planetPositionAtDate(
  body: string,
  dateStr: string
): [number, number, number] {
  const el = ELEMENTS[body.toLowerCase()];
  if (!el) return [0, 0, 0];

  const dateMs = new Date(dateStr + 'T12:00:00Z').getTime();
  const dtDays = (dateMs - J2000_MS) / 86400000;

  const n = (2 * Math.PI) / el.period_days;
  let M = el.m0 + n * dtDays;
  M = ((M % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  const E = solveKepler(M, el.e);

  // Position in the orbital plane (focus at origin, x axis to periapsis)
  const xOrb = el.a * (Math.cos(E) - el.e);
  const yOrb = el.a * Math.sqrt(1 - el.e * el.e) * Math.sin(E);

  // Rotate orbital → ecliptic: R_z(Ω) · R_x(i) · R_z(ω) · [xOrb, yOrb, 0]
  const cw  = Math.cos(el.w),  sw  = Math.sin(el.w);
  const ci  = Math.cos(el.i),  si  = Math.sin(el.i);
  const co  = Math.cos(el.om), so  = Math.sin(el.om);

  const x1 = xOrb * cw - yOrb * sw;
  const y1 = xOrb * sw + yOrb * cw;

  // R_x(i) (around line of nodes) — rotates y, z
  const y2 = y1 * ci;
  const z2 = y1 * si;

  // R_z(Ω)
  const x3 = x1 * co - y2 * so;
  const y3 = x1 * so + y2 * co;

  return [x3 * AU_KM, y3 * AU_KM, z2 * AU_KM];
}

/**
 * Positions for all modelled planets at a given date.
 */
export function allPlanetPositionsAtDate(dateStr: string): Record<string, [number, number, number]> {
  const result: Record<string, [number, number, number]> = {};
  for (const body of Object.keys(ELEMENTS)) {
    result[body] = planetPositionAtDate(body, dateStr);
  }
  return result;
}

/**
 * Interpolate a UTC date between two date strings by a [0, 1] progress fraction.
 */
export function interpolateDate(startDate: string, endDate: string, progress: number): string {
  const startMs = new Date(startDate + 'T12:00:00Z').getTime();
  const endMs   = new Date(endDate   + 'T12:00:00Z').getTime();
  const currentMs = startMs + progress * (endMs - startMs);
  return new Date(currentMs).toISOString().slice(0, 10);
}
