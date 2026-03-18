import { create } from 'zustand';
import type { PlanetState, TransferResult, PorkchopData, NHATSTarget, OrbitData } from '../lib/api';

export type ViewMode = 'solar-system' | 'porkchop' | 'targets' | 'guide';
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

  planets: [],
  setPlanets: (planets) => set({ planets }),
  orbits: new Map(),
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

  referenceMission: null,
  setReferenceMission: (m) => set({ referenceMission: m }),

  error: null,
  setError: (e) => set({ error: e }),
}));
