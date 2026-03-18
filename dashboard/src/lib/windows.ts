/**
 * Compute next optimal launch window based on planetary phase angles.
 *
 * For a Hohmann transfer, the optimal departure occurs when the phase angle
 * between departure and arrival bodies matches the geometry required for the
 * transfer orbit. This is basic mission design — a NASA trajectory engineer
 * would compute this from ephemeris data, but we can get a good approximation
 * from mean longitudes and Hohmann transfer time.
 */

export interface TransferWindow {
  depStart: string;
  depEnd: string;
  arrStart: string;
  arrEnd: string;
  depDate: string;
  arrDate: string;
  typicalTofDays: [number, number];
  hohmannTofDays: number;
  synodicMonths: number;
  note: string;
}

// Semi-major axes in AU
const SMA: Record<string, number> = {
  mercury: 0.387,
  venus: 0.723,
  earth: 1.000,
  mars: 1.524,
  jupiter: 5.203,
  saturn: 9.537,
};

// Orbital periods in days
const PERIODS: Record<string, number> = {
  mercury: 87.97,
  venus: 224.70,
  earth: 365.25,
  mars: 686.97,
  jupiter: 4332.59,
  saturn: 10759.22,
};

// Mean longitude at J2000 (degrees) — used as reference for phase angle computation
const MEAN_LON_J2000: Record<string, number> = {
  mercury: 252.25,
  venus: 181.98,
  earth: 100.46,
  mars: 355.45,
  jupiter: 34.40,
  saturn: 49.94,
};

// Typical TOF ranges (days) — wider than Hohmann to cover realistic transfers
const TOF_RANGES: Record<string, [number, number]> = {
  'earth-mercury': [80, 150],
  'earth-venus': [100, 250],
  'earth-mars': [200, 400],
  'earth-jupiter': [500, 1100],
  'earth-saturn': [1000, 2500],
};

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + Math.round(days));
  return d.toISOString().slice(0, 10);
}

/** Days from J2000 (2000-01-01T12:00:00) to a date string. */
function daysFromJ2000(dateStr: string): number {
  const j2000 = new Date('2000-01-01T12:00:00Z').getTime();
  const target = new Date(dateStr + 'T12:00:00Z').getTime();
  return (target - j2000) / 86400000;
}

/** Mean longitude of a body at a given date (degrees, 0-360). */
function meanLongitude(body: string, dateStr: string): number {
  const days = daysFromJ2000(dateStr);
  const period = PERIODS[body];
  const lon0 = MEAN_LON_J2000[body];
  // Mean motion in deg/day
  const n = 360 / period;
  return ((lon0 + n * days) % 360 + 360) % 360;
}

/** Phase angle between two bodies (target longitude - departure longitude, in degrees 0-360). */
function phaseAngle(from: string, to: string, dateStr: string): number {
  const lonFrom = meanLongitude(from, dateStr);
  const lonTo = meanLongitude(to, dateStr);
  return ((lonTo - lonFrom) % 360 + 360) % 360;
}

/** Hohmann transfer time in days. */
function hohmannTOF(fromBody: string, toBody: string): number {
  const a1 = SMA[fromBody];
  const a2 = SMA[toBody];
  // Hohmann transfer = half ellipse with a_transfer = (a1 + a2) / 2
  // By Kepler's third law (AU, years): T_orbit = sqrt(a^3) years
  // Half orbit: T_hohmann = sqrt(a_transfer^3) / 2 years
  const aTransfer = (a1 + a2) / 2;
  const tYears = Math.sqrt(aTransfer ** 3) / 2;
  return tYears * 365.25;
}

/**
 * Optimal phase angle at departure for a Hohmann transfer.
 * φ_opt = 180° - (T_transfer / T_target) * 180°
 * For outer planets (from inner): we want the target to be "ahead" by this angle.
 * For inner planets (from outer): geometry reverses.
 */
function optimalPhaseAngle(fromBody: string, toBody: string): number {
  const tTransfer = hohmannTOF(fromBody, toBody);
  const isOutbound = SMA[toBody] > SMA[fromBody];
  const tTarget = isOutbound ? PERIODS[toBody] : PERIODS[fromBody];
  // Phase angle the target needs to be ahead of departure body
  const phi = 180 - (tTransfer / tTarget) * 180;
  return ((phi % 360) + 360) % 360;
}

/** Synodic period in days. */
function synodicPeriod(p1: number, p2: number): number {
  return Math.abs(1 / (1 / p1 - 1 / p2));
}

/**
 * Find the next date (from epoch) when the phase angle matches the optimal
 * Hohmann geometry. Searches forward up to one full synodic period.
 */
function nextOptimalDeparture(from: string, to: string, epoch: string): string {
  const phiOpt = optimalPhaseAngle(from, to);
  const synodic = synodicPeriod(PERIODS[from], PERIODS[to]);

  // Sample phase angle daily over one synodic period, find closest match
  let bestDay = 0;
  let bestDiff = 999;

  // Search forward up to 1.2 synodic periods
  const searchDays = Math.round(synodic * 1.2);
  for (let d = 0; d <= searchDays; d++) {
    const testDate = addDays(epoch, d);
    const phi = phaseAngle(from, to, testDate);
    // Angular difference (shortest arc)
    const diff = Math.min(
      Math.abs(phi - phiOpt),
      360 - Math.abs(phi - phiOpt)
    );
    if (diff < bestDiff) {
      bestDiff = diff;
      bestDay = d;
    }
  }

  return addDays(epoch, bestDay);
}

export function suggestWindow(from: string, to: string, epoch: string): TransferWindow {
  const key = `${from}-${to}`;
  const reverseKey = `${to}-${from}`;
  const tofRange = TOF_RANGES[key] || TOF_RANGES[reverseKey];

  const p1 = PERIODS[from] || 365;
  const p2 = PERIODS[to] || 365;
  const synodic = synodicPeriod(p1, p2);
  const synodicMonths = Math.round(synodic / 30);
  const hohmann = Math.round(hohmannTOF(from, to));

  if (from === to) {
    return {
      depStart: epoch, depEnd: addDays(epoch, 365),
      arrStart: epoch, arrEnd: addDays(epoch, 365),
      depDate: addDays(epoch, 30), arrDate: addDays(epoch, 60),
      typicalTofDays: [1, 365], hohmannTofDays: 0, synodicMonths: 0,
      note: 'Same body — no transfer needed',
    };
  }

  // Find the next optimal departure from phase angle geometry
  const depDate = nextOptimalDeparture(from, to, epoch);
  const arrDate = addDays(depDate, hohmann);

  // Porkchop search window: center on optimal departure, span ~40% of synodic period
  const searchSpan = Math.round(synodic * 0.4);
  const depStart = addDays(depDate, -Math.round(searchSpan / 2));
  const depEnd = addDays(depDate, Math.round(searchSpan / 2));

  const [tofMin, tofMax] = tofRange || [
    Math.round(hohmann * 0.6),
    Math.round(hohmann * 1.6),
  ];
  const arrStart = addDays(depStart, tofMin);
  const arrEnd = addDays(depEnd, tofMax);

  return {
    depStart, depEnd, arrStart, arrEnd,
    depDate, arrDate,
    typicalTofDays: [tofMin, tofMax],
    hohmannTofDays: hohmann,
    synodicMonths,
    note: `Windows every ~${synodicMonths} mo | Hohmann TOF ${hohmann}d`,
  };
}
