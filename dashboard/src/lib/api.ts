const API_BASE = '/api';

export interface PlanetState {
  name: string;
  position: [number, number, number];
  velocity: [number, number, number];
  distance_au: number;
  speed_kms: number;
}

export interface TransferResult {
  departure_body: string;
  arrival_body: string;
  departure_utc: string;
  arrival_utc: string;
  tof_days: number;
  dv_departure: number;
  dv_arrival: number;
  dv_total: number;
  c3_launch: number;
  v_inf_arrival: number;
  trajectory_positions: [number, number, number][];
}

export interface PorkchopData {
  departure_body: string;
  arrival_body: string;
  dep_dates: string[];
  arr_dates: string[];
  dv_total: (number | null)[][];
  c3_launch: (number | null)[][];
  tof_days: (number | null)[][];
  optimal: {
    dep_utc: string;
    arr_utc: string;
    dv_total: number;
    c3_launch: number;
    tof_days: number;
  } | null;
  resolution: number;
}

export interface OrbitData {
  body: string;
  positions: [number, number, number][];
  period_days: number;
}

export interface NHATSTarget {
  des: string;
  fullname: string;
  h: number;
  min_dv: number;
  min_dv_dur: number;
  min_dur: number;
  n_via: number;
  min_size_m: number;
  max_size_m: number;
}

async function fetchJSON<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function getPlanets(epoch: string): Promise<PlanetState[]> {
  return fetchJSON(`${API_BASE}/planets/${encodeURIComponent(epoch)}`);
}

export async function getOrbit(body: string, epoch: string = '2026-01-01'): Promise<OrbitData> {
  return fetchJSON(`${API_BASE}/planets/${body}/orbit?epoch=${encodeURIComponent(epoch)}`);
}

export async function getTransfer(
  depBody: string, arrBody: string,
  depDate: string, arrDate: string
): Promise<TransferResult> {
  const params = new URLSearchParams({
    departure_body: depBody,
    arrival_body: arrBody,
    departure_date: depDate,
    arrival_date: arrDate,
  });
  return fetchJSON(`${API_BASE}/transfer?${params}`);
}

export async function getPorkchop(
  depBody: string, arrBody: string,
  depStart: string, depEnd: string,
  arrStart: string, arrEnd: string,
  resolution: number = 80
): Promise<PorkchopData> {
  const params = new URLSearchParams({
    departure_body: depBody,
    arrival_body: arrBody,
    dep_start: depStart,
    dep_end: depEnd,
    arr_start: arrStart,
    arr_end: arrEnd,
    resolution: String(resolution),
  });
  return fetchJSON(`${API_BASE}/porkchop?${params}`);
}

export async function getTargets(maxDv: number = 6, limit: number = 50): Promise<{
  count: number;
  targets: NHATSTarget[];
}> {
  return fetchJSON(`${API_BASE}/targets?max_dv=${maxDv}&limit=${limit}`);
}

// --- Reference Missions ---

export interface MissionEvent {
  body: string;
  date: string;
  type: string;
  distance_km: number;
  dv_gained: number;
}

export interface ReferenceMission {
  name: string;
  description: string;
  sequence: string[];
  events: MissionEvent[];
  trajectory_positions: [number, number, number][];
}

export async function getReferenceMissions(): Promise<ReferenceMission[]> {
  return fetchJSON(`${API_BASE}/reference-missions`);
}

export async function getReferenceMission(name: string): Promise<ReferenceMission> {
  return fetchJSON(`${API_BASE}/reference-missions/${encodeURIComponent(name)}`);
}

// --- NEA Transfers ---

export async function getNeaTransfer(
  designation: string, depDate: string, arrDate: string
): Promise<TransferResult> {
  const params = new URLSearchParams({ designation, departure_date: depDate, arrival_date: arrDate });
  return fetchJSON(`${API_BASE}/nea/transfer?${params}`);
}

export async function getNeaPorkchop(
  designation: string,
  depStart: string, depEnd: string,
  arrStart: string, arrEnd: string,
  resolution: number = 40
): Promise<PorkchopData> {
  const params = new URLSearchParams({
    designation, dep_start: depStart, dep_end: depEnd,
    arr_start: arrStart, arr_end: arrEnd, resolution: String(resolution),
  });
  return fetchJSON(`${API_BASE}/nea/porkchop?${params}`);
}

// --- Optimization ---

export interface OptimizeRequest {
  sequence: string[];
  dep_start: string;
  dep_end: string;
  tof_bounds: [number, number][];
  v_inf_max?: number;
  max_iter?: number;
  pop_size?: number;
}

export interface OptimizeResult {
  sequence: string[];
  total_dv: number;
  departure_v_inf: number;
  arrival_v_inf: number;
  c3_launch: number;
  departure_utc: string;
  arrival_utc: string;
  total_tof_days: number;
  legs: {
    from: string;
    to: string;
    tof_days: number;
    dsm_dv: number;
    trajectory_positions?: [number, number, number][];
  }[];
  optimizer: { success: boolean; message: string; n_evaluations: number };
}

export async function optimizeTrajectory(req: OptimizeRequest): Promise<OptimizeResult> {
  const resp = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}
