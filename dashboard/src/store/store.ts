import { create } from 'zustand';
import type { PlanetState, TransferResult, PorkchopData, NHATSTarget, OrbitData } from '../lib/api';
import { allPlanetPositionsAtDate, planetPositionAtDate } from '../lib/orbits';

export type ViewMode = 'solar-system' | 'porkchop' | 'targets' | 'guide';

// Compute approximate planet positions client-side so they render instantly
// (before the API cold-starts). API response overwrites with precise positions.
const INITIAL_EPOCH = '2026-03-15';
const approxPositions = allPlanetPositionsAtDate(INITIAL_EPOCH);
const initialPlanets: PlanetState[] = Object.entries(approxPositions).map(([name, position]) => ({
  name,
  position,
  velocity: [0, 0, 0],
  distance_au: Math.sqrt(position[0] ** 2 + position[1] ** 2 + position[2] ** 2) / 1.496e8,
  speed_kms: 0,
}));

// Generate approximate orbit paths client-side for instant rendering
function generateApproxOrbit(body: string, steps: number = 128): OrbitData {
  const startDate = new Date('2026-01-01T12:00:00Z');
  // Look up period from orbits.ts constants (mirrored here for orbit generation)
  const periods: Record<string, number> = {
    mercury: 87.97, venus: 224.7, earth: 365.25, mars: 686.97,
  };
  const periodDays = periods[body] || 365.25;
  const positions: [number, number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const date = new Date(startDate.getTime() + (i / steps) * periodDays * 86400000);
    const dateStr = date.toISOString().slice(0, 10);
    positions.push(planetPositionAtDate(body, dateStr));
  }
  return { body, positions, period_days: periodDays };
}

const initialOrbits = new Map<string, OrbitData>();
for (const body of ['mercury', 'venus', 'earth', 'mars']) {
  initialOrbits.set(body, generateApproxOrbit(body));
}

export type CameraPreset = 'default' | 'top-down' | 'inner-system' | 'outer-system';

interface AppState {
  initialized: boolean;
  setInitialized: (v: boolean) => void;

  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;

  epoch: string;
  setEpoch: (epoch: string) => void;

  planets: PlanetState[];
  setPlanets: (planets: PlanetState[]) => void;
  orbits: Map<string, OrbitData>;
  setOrbit: (body: string, orbit: OrbitData) => void;

  departureBody: string;
  arrivalBody: string;
  departureDate: string;
  arrivalDate: string;
  setDepartureBody: (body: string) => void;
  setArrivalBody: (body: string) => void;
  setDepartureDate: (date: string) => void;
  setArrivalDate: (date: string) => void;
  transfer: TransferResult | null;
  setTransfer: (t: TransferResult | null) => void;
  transferLoading: boolean;
  setTransferLoading: (loading: boolean) => void;

  porkchop: PorkchopData | null;
  setPorkchop: (data: PorkchopData | null) => void;
  porkchopLoading: boolean;
  setPorkchopLoading: (loading: boolean) => void;
  porkDepStart: string;
  porkDepEnd: string;
  porkArrStart: string;
  porkArrEnd: string;
  setPorkDepStart: (d: string) => void;
  setPorkDepEnd: (d: string) => void;
  setPorkArrStart: (d: string) => void;
  setPorkArrEnd: (d: string) => void;

  targets: NHATSTarget[];
  setTargets: (targets: NHATSTarget[]) => void;
  targetsLoading: boolean;
  setTargetsLoading: (loading: boolean) => void;
  selectedTarget: NHATSTarget | null;
  setSelectedTarget: (target: NHATSTarget | null) => void;
  maxDvFilter: number;
  setMaxDvFilter: (dv: number) => void;

  // Camera
  cameraTarget: string | null;
  setCameraTarget: (body: string | null) => void;
  cameraPreset: CameraPreset | null;
  setCameraPreset: (preset: CameraPreset | null) => void;

  // Trajectory animation
  animationProgress: number; // 0-1
  setAnimationProgress: (p: number) => void;
  animationPlaying: boolean;
  setAnimationPlaying: (p: boolean) => void;
  cinematicMode: boolean;
  setCinematicMode: (v: boolean) => void;
  activeFlybyIndex: number | null; // index into referenceMission.flybys[] or null
  setActiveFlybyIndex: (i: number | null) => void;

  // Reference mission (full data for timeline/flyby markers)
  referenceMission: any | null;
  setReferenceMission: (m: any | null) => void;

  error: string | null;
  setError: (e: string | null) => void;
}

export const useStore = create<AppState>((set) => ({
  initialized: false,
  setInitialized: (v) => set({ initialized: v }),

  viewMode: 'solar-system',
  setViewMode: (mode) => set({ viewMode: mode }),

  epoch: '2026-03-15',
  setEpoch: (epoch) => set({ epoch }),

  planets: initialPlanets,
  setPlanets: (planets) => set({ planets }),
  orbits: initialOrbits,
  setOrbit: (body, orbit) => set((state) => {
    const orbits = new Map(state.orbits);
    orbits.set(body, orbit);
    return { orbits };
  }),

  departureBody: 'earth',
  arrivalBody: 'mars',
  departureDate: '2026-10-30',
  arrivalDate: '2027-09-05',
  setDepartureBody: (body) => set({ departureBody: body }),
  setArrivalBody: (body) => set({ arrivalBody: body }),
  setDepartureDate: (date) => set({ departureDate: date }),
  setArrivalDate: (date) => set({ arrivalDate: date }),
  transfer: null,
  setTransfer: (t) => set({ transfer: t, animationProgress: 0, animationPlaying: false }),
  transferLoading: false,
  setTransferLoading: (loading) => set({ transferLoading: loading }),

  porkchop: null,
  setPorkchop: (data) => set({ porkchop: data }),
  porkchopLoading: false,
  setPorkchopLoading: (loading) => set({ porkchopLoading: loading }),
  porkDepStart: '2026-08-01',
  porkDepEnd: '2027-02-01',
  porkArrStart: '2027-04-01',
  porkArrEnd: '2027-12-01',
  setPorkDepStart: (d) => set({ porkDepStart: d }),
  setPorkDepEnd: (d) => set({ porkDepEnd: d }),
  setPorkArrStart: (d) => set({ porkArrStart: d }),
  setPorkArrEnd: (d) => set({ porkArrEnd: d }),

  targets: [],
  setTargets: (targets) => set({ targets }),
  targetsLoading: false,
  setTargetsLoading: (loading) => set({ targetsLoading: loading }),
  selectedTarget: null,
  setSelectedTarget: (target) => set({ selectedTarget: target }),
  maxDvFilter: 6,
  setMaxDvFilter: (dv) => set({ maxDvFilter: dv }),

  cameraTarget: null,
  setCameraTarget: (body) => set({ cameraTarget: body }),
  cameraPreset: null,
  setCameraPreset: (preset) => set({ cameraPreset: preset }),

  animationProgress: 0,
  setAnimationProgress: (p) => set({ animationProgress: p }),
  animationPlaying: false,
  setAnimationPlaying: (p) => set({ animationPlaying: p }),
  cinematicMode: true,
  setCinematicMode: (v) => set({ cinematicMode: v }),
  activeFlybyIndex: null,
  setActiveFlybyIndex: (i) => set({ activeFlybyIndex: i }),

  referenceMission: null,
  setReferenceMission: (m) => set({ referenceMission: m }),

  error: null,
  setError: (e) => set({ error: e }),
}));
