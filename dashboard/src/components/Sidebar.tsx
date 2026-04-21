import { useState, useMemo, useEffect } from 'react';
import { useStore } from '../store/store';
import { getTransfer, getPlanets, getOrbit, getPorkchop, getTargets, getReferenceMission, getNeaPorkchop, getGTOPBenchmark, getDesignedMission } from '../lib/api';
import type { PlanetState } from '../lib/api';
import { suggestWindow } from '../lib/windows';
import type { TransferWindow } from '../lib/windows';
import { allPlanetPositionsAtDate } from '../lib/orbits';
// ReferenceMission type used implicitly via getReferenceMission

const BODIES = ['mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn'];

function addDaysStr(dateStr: string, days: number): string {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

// --- Mission library ---

type MissionCategory = 'historic' | 'benchmark' | 'designed';
type PropulsionType = 'chemical' | 'ion' | 'sail' | 'hybrid';

interface LibraryMission {
  id: string;
  label: string;
  sub: string;
  detail?: string;
  category: MissionCategory;
  propulsion: PropulsionType;
}

const MISSIONS: LibraryMission[] = [
  // Historic — chemical
  { id: 'voyager', label: 'Voyager 2', sub: 'E→J→S→U→N', detail: '1977-1989 · NASA', category: 'historic', propulsion: 'chemical' },
  { id: 'cassini', label: 'Cassini', sub: 'E→V→V→E→J→S', detail: '1997-2017 · NASA/ESA', category: 'historic', propulsion: 'chemical' },
  { id: 'new horizons', label: 'New Horizons', sub: 'E→J→Pluto', detail: '2006-2015 · NASA', category: 'historic', propulsion: 'chemical' },
  { id: 'galileo', label: 'Galileo', sub: 'E→V→E→E→J', detail: '1989-2003 · NASA', category: 'historic', propulsion: 'chemical' },
  { id: 'mariner', label: 'Mariner 10', sub: 'E→V→Mercury', detail: '1973-1975 · NASA', category: 'historic', propulsion: 'chemical' },
  { id: 'juno', label: 'Juno', sub: 'E→E→J', detail: '2011– · NASA', category: 'historic', propulsion: 'chemical' },
  { id: 'pioneer', label: 'Pioneer 10', sub: 'E→J', detail: '1972-2003 · NASA', category: 'historic', propulsion: 'chemical' },
  { id: 'messenger', label: 'MESSENGER', sub: 'E→E→V→V→M×4', detail: '2004-2015 · NASA', category: 'historic', propulsion: 'chemical' },
  // Historic — ion / sail / hybrid
  { id: 'dawn', label: 'Dawn', sub: 'E→Ma→Vesta→Ceres', detail: '2007-2018 · NASA', category: 'historic', propulsion: 'ion' },
  { id: 'hayabusa2', label: 'Hayabusa2', sub: 'E→Ryugu→E', detail: '2014-2020 · JAXA', category: 'historic', propulsion: 'ion' },
  { id: 'hayabusa', label: 'Hayabusa', sub: 'E→Itokawa→E', detail: '2003-2010 · JAXA', category: 'historic', propulsion: 'ion' },
  { id: 'psyche', label: 'Psyche', sub: 'E→Ma→Psyche', detail: '2023-2029 · NASA', category: 'historic', propulsion: 'ion' },
  { id: 'bepicolombo', label: 'BepiColombo', sub: '9 GAs → Mercury', detail: '2018-2025 · ESA/JAXA', category: 'historic', propulsion: 'hybrid' },
  { id: 'ikaros', label: 'IKAROS', sub: 'E→Venus', detail: '2010 · JAXA', category: 'historic', propulsion: 'sail' },
  // Benchmark — GTOP
  { id: 'cassini2', label: 'Cassini2', sub: 'E→V→V→E→J→S', detail: 'Best: 8.383 km/s', category: 'benchmark', propulsion: 'chemical' },
  { id: 'messenger', label: 'Messenger', sub: 'E→E→V→V→Me', detail: 'Best: 8.630 km/s', category: 'benchmark', propulsion: 'chemical' },
  { id: 'rosetta', label: 'Rosetta', sub: 'E→E→Ma→E→E→67P', detail: 'Best: 1.343 km/s', category: 'benchmark', propulsion: 'chemical' },
  // Designed — chemical
  { id: 'grand-tour-eejs', label: 'Grand Tour: EEJS', sub: 'E→E→J→S', detail: '8.80 km/s · 13.4yr', category: 'designed', propulsion: 'chemical' },
  { id: 'grand-tour-vejs', label: 'Grand Tour: VEJS', sub: 'E→V→E→J→S', detail: '9.04 km/s · 12.2yr', category: 'designed', propulsion: 'chemical' },
  { id: 'fast-jupiter-vej', label: 'Jupiter: VEJ', sub: 'E→V→E→J', detail: '10.18 km/s · 4.6yr', category: 'designed', propulsion: 'chemical' },
  { id: 'jupiter-emaj', label: 'Jupiter: EMaJ', sub: 'E→E→Ma→J', detail: '10.07 km/s · 6.0yr', category: 'designed', propulsion: 'chemical' },
  { id: 'jupiter-maej', label: 'Jupiter: MaEJ', sub: 'E→Ma→E→J', detail: '10.66 km/s · 6.5yr', category: 'designed', propulsion: 'chemical' },
  { id: 'sample-return-sg344', label: 'Sample Return: SG344', sub: 'E→SG344→E', detail: '1.83 km/s · 2.1yr', category: 'designed', propulsion: 'chemical' },
  { id: 'sample-return-hu4', label: 'Sample Return: HU4', sub: 'E→HU4→E', detail: '3.92 km/s · 1.9yr', category: 'designed', propulsion: 'chemical' },
  { id: 'sample-return-ao10', label: 'Sample Return: AO10', sub: 'E→AO10→E', detail: '5.91 km/s · 1.6yr', category: 'designed', propulsion: 'chemical' },
  { id: 'interstellar-vej', label: 'Interstellar: VEJ', sub: 'E→V→E→J→∞', detail: '7.40 AU/yr · 200 AU/27yr', category: 'designed', propulsion: 'chemical' },
  { id: 'tour-sg344-rh120', label: 'Tour: SG344→RH120', sub: 'E→SG344→RH120→E', detail: '3.71 km/s · 2.5yr', category: 'designed', propulsion: 'chemical' },
  { id: 'halley-2061-flyby', label: "Halley's Comet Flyby 2061", sub: 'Retrograde flyby', detail: '47.7 km/s · 1.7yr', category: 'designed', propulsion: 'chemical' },
  // Designed — ion
  { id: 'lt-earth-mars', label: 'Low-Thrust: Earth→Mars', sub: 'Ion, E→Mars', detail: '223 kg Xe · 400d · 4.71 km/s', category: 'designed', propulsion: 'ion' },
  { id: 'lt-earth-vesta', label: 'Low-Thrust: Earth→Vesta', sub: 'Ion, Dawn-like', detail: '350 kg Xe · 1300d · 9.18 km/s', category: 'designed', propulsion: 'ion' },
  { id: 'lt-apophis', label: 'Low-Thrust: Apophis Rendezvous', sub: 'Ion, pre-2029 flyby', detail: '265 kg Xe · arrive Jan 2029', category: 'designed', propulsion: 'ion' },
  { id: 'lt-chiron', label: 'Low-Thrust: Chiron Orbiter', sub: 'First Centaur orbiter', detail: '12.3yr · 1200 kg Xe · 14 AU', category: 'designed', propulsion: 'ion' },
  { id: 'lt-sr-bennu', label: 'Low-Thrust Sample Return: Bennu', sub: 'Ion OSIRIS-REx', detail: '3.8yr · 400 kg Xe', category: 'designed', propulsion: 'ion' },
  // Designed — sail
  { id: 'sail-interstellar', label: 'Solar Sail: Interstellar', sub: 'Zero propellant', detail: '15.5 km/s · 3.3 AU/yr', category: 'designed', propulsion: 'sail' },
  { id: 'sail-polar-observer', label: 'Solar Sail: Polar Observer', sub: 'Crank inclination', detail: '6yr · 134° · no fuel', category: 'designed', propulsion: 'sail' },
  // Designed — hybrid
  { id: 'hybrid-mars-capture', label: 'Hybrid: Mars Capture', sub: 'Ion + chemical OI', detail: '1.77 km/s chem Δv', category: 'designed', propulsion: 'hybrid' },
  { id: 'hybrid-saturn', label: 'Hybrid: Saturn', sub: 'Cassini-class', detail: '7.7yr · 1200 kg Xe', category: 'designed', propulsion: 'hybrid' },
  { id: 'hybrid-pluto', label: 'Hybrid: Pluto Orbiter', sub: 'Faster NH + orbit', detail: '12yr · 1500 kg Xe', category: 'designed', propulsion: 'hybrid' },
  { id: 'hybrid-triton', label: 'Hybrid: Neptune/Triton', sub: 'Reach mission', detail: '15yr · 30 AU · post-V2', category: 'designed', propulsion: 'hybrid' },
];

const CATEGORY_META: Record<MissionCategory, { label: string; accent: string; verb: string; hint: string }> = {
  historic: { label: 'Historic', accent: 'var(--amber)', verb: 'Building', hint: 'Missions that actually flew' },
  benchmark: { label: 'Benchmark', accent: 'var(--green)', verb: 'Optimizing', hint: 'ESA GTOP problems (~30–60s)' },
  designed: { label: 'Designed', accent: '#8b5cf6', verb: 'Loading', hint: 'Novel trajectories from I.C.A.R.U.S.' },
};

const PROPULSION_META: Record<PropulsionType, { label: string; accent: string }> = {
  chemical: { label: 'Chemical', accent: '#f59e0b' },
  ion: { label: 'Ion', accent: '#3b82f6' },
  sail: { label: 'Sail', accent: '#10b981' },
  hybrid: { label: 'Hybrid', accent: '#a855f7' },
};

function chipStyle(active: boolean): React.CSSProperties {
  return {
    padding: '3px 9px',
    background: active ? 'var(--text-secondary)' : 'transparent',
    color: active ? 'var(--bg)' : 'var(--text-dim)',
    border: '1px solid var(--panel-border)',
    borderRadius: '10px',
    cursor: 'pointer',
    fontFamily: 'var(--font-mono)',
    fontSize: '9px',
    letterSpacing: '0.3px',
    fontWeight: active ? 600 : 400,
  };
}

export function Sidebar() {
  const s = useStore();
  const [windowsExpanded, setWindowsExpanded] = useState(false);

  // Mission Library state (unified — replaces the four per-category sections)
  const [libExpanded, setLibExpanded] = useState(false);
  const [libCategory, setLibCategory] = useState<MissionCategory>('designed');
  const [libPropulsion, setLibPropulsion] = useState<PropulsionType | 'all'>('all');
  const [missionLoading, setMissionLoading] = useState<string | null>(null);

  const filteredMissions = useMemo(() => MISSIONS.filter(
    m => m.category === libCategory && (libPropulsion === 'all' || m.propulsion === libPropulsion)
  ), [libCategory, libPropulsion]);

  const availablePropulsions = useMemo(() => {
    const types = new Set<PropulsionType>();
    MISSIONS.forEach(m => { if (m.category === libCategory) types.add(m.propulsion); });
    return Array.from(types);
  }, [libCategory]);

  const categoryCounts = useMemo(() => {
    const counts: Record<MissionCategory, number> = { historic: 0, benchmark: 0, designed: 0 };
    MISSIONS.forEach(m => { counts[m.category]++; });
    return counts;
  }, []);

  const applyWindow = (from: string, to: string) => {
    const state = useStore.getState();
    const w = suggestWindow(from, to, state.epoch);
    useStore.setState({
      departureDate: w.depDate,
      arrivalDate: w.arrDate,
      porkDepStart: w.depStart,
      porkDepEnd: w.depEnd,
      porkArrStart: w.arrStart,
      porkArrEnd: w.arrEnd,
      transfer: null,
      porkchop: null,
    });
  };

  const handleDepartureBody = (body: string) => {
    s.setDepartureBody(body);
    applyWindow(body, s.arrivalBody);
  };

  const handleArrivalBody = (body: string) => {
    s.setArrivalBody(body);
    applyWindow(s.departureBody, body);
  };

  const window = suggestWindow(s.departureBody, s.arrivalBody, s.epoch);

  // Compute upcoming transfer windows (next 5)
  const upcomingWindows = useMemo(() => {
    const windows: TransferWindow[] = [];
    // Start searching from current epoch
    let searchEpoch = s.epoch;
    for (let i = 0; i < 5; i++) {
      const w = suggestWindow(s.departureBody, s.arrivalBody, searchEpoch);
      // Deduplicate: skip if same departure date as the currently selected or previous window
      const isDupe = w.depDate === s.departureDate ||
        windows.some(prev => Math.abs(new Date(prev.depDate).getTime() - new Date(w.depDate).getTime()) < 30 * 86400000);
      if (isDupe) {
        // Advance past this window by ~60% of synodic period to reach next one
        searchEpoch = addDaysStr(w.depDate, Math.max(60, w.synodicMonths * 15));
        i--; // Don't count this iteration
        if (i < -5) break; // Safety valve
        continue;
      }
      windows.push(w);
      // Advance past this window to find the next one
      searchEpoch = addDaysStr(w.depDate, Math.max(60, w.synodicMonths * 15));
    }
    return windows;
  }, [s.departureBody, s.arrivalBody, s.epoch, s.departureDate]);

  const loadPlanets = async () => {
    try {
      s.setError(null);
      const planets = await getPlanets(s.epoch);
      s.setPlanets(planets);
      const orbitBodies = ['mercury', 'venus', 'earth', 'mars', 'ceres', 'vesta',
        'jupiter', 'saturn', 'uranus', 'neptune', 'pluto', 'eris', 'haumea', 'makemake'];
      for (const body of orbitBodies) {
        getOrbit(body, s.epoch).then(orbit => s.setOrbit(body, orbit)).catch(() => {});
      }
    } catch (e) { s.setError(String(e)); }
  };

  const computeTransfer = async () => {
    s.setError(null);
    s.setTransferLoading(true);
    s.setReferenceMission(null);
    try {
      const result = await getTransfer(s.departureBody, s.arrivalBody, s.departureDate, s.arrivalDate);
      s.setTransfer(result);
      s.setViewMode('solar-system');
    } catch (e) { s.setError(String(e)); }
    finally { s.setTransferLoading(false); }
  };

  const computePorkchop = async () => {
    s.setError(null);
    s.setPorkchopLoading(true);
    try {
      const result = await getPorkchop(
        s.departureBody, s.arrivalBody,
        s.porkDepStart, s.porkDepEnd,
        s.porkArrStart, s.porkArrEnd, 60
      );
      s.setPorkchop(result);
      s.setViewMode('porkchop');
    } catch (e) { s.setError(String(e)); }
    finally { s.setPorkchopLoading(false); }
  };

  const loadTargets = async () => {
    s.setError(null);
    s.setTargetsLoading(true);
    try {
      const data = await getTargets(s.maxDvFilter, 200);
      s.setTargets(data.targets);
      s.setViewMode('targets');
    } catch (e) { s.setError(String(e)); }
    finally { s.setTargetsLoading(false); }
  };

  const loadMission = async (m: LibraryMission) => {
    const key = `${m.category}:${m.id}`;
    setMissionLoading(key);
    try {
      const mission =
        m.category === 'historic' ? await getReferenceMission(m.id)
        : m.category === 'benchmark' ? await getGTOPBenchmark(m.id)
        : await getDesignedMission(m.id);
      const launchDate = mission.events[0]?.date || '';
      const approx = allPlanetPositionsAtDate(launchDate);
      const approxPlanets: PlanetState[] = Object.entries(approx).map(([name, position]) => ({
        name, position, velocity: [0, 0, 0] as [number, number, number],
        distance_au: Math.sqrt(position[0] ** 2 + position[1] ** 2 + position[2] ** 2) / 1.496e8,
        speed_kms: 0,
      }));
      useStore.setState({
        planets: approxPlanets,
        transfer: {
          departure_body: mission.sequence[0],
          arrival_body: mission.sequence[mission.sequence.length - 1],
          departure_utc: launchDate,
          arrival_utc: mission.events[mission.events.length - 1]?.date || '',
          tof_days: 0,
          dv_departure: 0, dv_arrival: 0, dv_total: (mission as { stats?: { total_dv_km_s?: number } }).stats?.total_dv_km_s || 0,
          c3_launch: 0, v_inf_arrival: 0,
          trajectory_positions: mission.trajectory_positions,
        },
        referenceMission: mission,
        viewMode: 'solar-system',
        animationProgress: 0,
        animationPlaying: false,
        epoch: launchDate,
      });
      getPlanets(launchDate).then(p => s.setPlanets(p)).catch(() => {});
      for (const body of ['mercury', 'venus', 'earth', 'mars', 'ceres', 'vesta',
        'jupiter', 'saturn', 'uranus', 'neptune', 'pluto', 'eris', 'haumea', 'makemake']) {
        getOrbit(body, launchDate).then(orbit => s.setOrbit(body, orbit)).catch(() => {});
      }
    } catch (e) { s.setError(String(e)); }
    finally { setMissionLoading(null); }
  };

  return (
    <div className="sidebar">
      {/* Epoch — inline one-line */}
      <div className="panel" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div className="panel-header-dot" />
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 600,
          letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--text-dim)',
        }}>
          Epoch
        </span>
        <input type="date" value={s.epoch} onChange={(e) => s.setEpoch(e.target.value)} className="input flex-1" />
        <button onClick={loadPlanets} className="btn btn-sm btn-ghost">
          {s.planets.length > 0 ? 'Reload' : 'Load'}
        </button>
      </div>

      {/* Transfer configuration */}
      <div className="panel">
        <div className="panel-header"><div className="panel-header-dot" />Transfer</div>
        <div className="grid-2">
          <div>
            <div className="field-label">Origin</div>
            <select value={s.departureBody} onChange={(e) => handleDepartureBody(e.target.value)} className="input">
              {BODIES.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div>
            <div className="field-label">Destination</div>
            <select value={s.arrivalBody} onChange={(e) => handleArrivalBody(e.target.value)} className="input">
              {BODIES.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
        </div>
        <div className="window-hint">
          {window.synodicMonths}mo &middot; {window.hohmannTofDays}d Hohmann &middot; {window.typicalTofDays[0]}&ndash;{window.typicalTofDays[1]}d
        </div>
        <div className="grid-2" style={{ marginTop: '6px' }}>
          <div>
            <div className="field-label">Departure</div>
            <input type="date" value={s.departureDate} onChange={(e) => s.setDepartureDate(e.target.value)} className="input" />
          </div>
          <div>
            <div className="field-label">Arrival</div>
            <input type="date" value={s.arrivalDate} onChange={(e) => s.setArrivalDate(e.target.value)} className="input" />
          </div>
        </div>
        <div className="row" style={{ marginTop: '8px', gap: '4px' }}>
          <button onClick={computeTransfer} className="btn flex-1" disabled={s.transferLoading}>
            {s.transferLoading ? 'Computing...' : 'Compute'}
          </button>
          <button onClick={computePorkchop} className="btn btn-ghost flex-1" disabled={s.porkchopLoading}>
            {s.porkchopLoading ? 'Generating...' : 'Porkchop'}
          </button>
        </div>

        {/* Upcoming windows */}
        <div style={{ marginTop: '8px' }}>
          <button
            onClick={() => setWindowsExpanded(!windowsExpanded)}
            style={{
              display: 'flex', alignItems: 'center', gap: '4px', width: '100%',
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0',
              fontFamily: 'var(--font-mono)', fontSize: '9px', letterSpacing: '0.6px',
              textTransform: 'uppercase', color: 'var(--text-dim)',
            }}
          >
            <span style={{ fontSize: '8px', transform: windowsExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>▶</span>
            Upcoming Windows
          </button>
          {windowsExpanded && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '4px' }}>
              {upcomingWindows.map((w, i) => (
                <button
                  key={i}
                  onClick={() => {
                    useStore.setState({
                      departureDate: w.depDate,
                      arrivalDate: w.arrDate,
                      porkDepStart: w.depStart,
                      porkDepEnd: w.depEnd,
                      porkArrStart: w.arrStart,
                      porkArrEnd: w.arrEnd,
                      transfer: null,
                      porkchop: null,
                    });
                  }}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '5px 8px', background: 'var(--void)', border: '1px solid var(--panel-border)',
                    borderRadius: '3px', cursor: 'pointer', textAlign: 'left',
                  }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-secondary)' }}>
                    {w.depDate}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)' }}>
                    {w.hohmannTofDays}d
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Porkchop fine-tuning (collapsed by default) */}
      {s.viewMode === 'porkchop' && (
        <div className="panel">
          <div className="panel-header"><div className="panel-header-dot" />Search Window</div>
          <div className="grid-2">
            <div>
              <div className="field-label">Dep Start</div>
              <input type="date" value={s.porkDepStart} onChange={(e) => s.setPorkDepStart(e.target.value)} className="input" />
            </div>
            <div>
              <div className="field-label">Dep End</div>
              <input type="date" value={s.porkDepEnd} onChange={(e) => s.setPorkDepEnd(e.target.value)} className="input" />
            </div>
            <div>
              <div className="field-label">Arr Start</div>
              <input type="date" value={s.porkArrStart} onChange={(e) => s.setPorkArrStart(e.target.value)} className="input" />
            </div>
            <div>
              <div className="field-label">Arr End</div>
              <input type="date" value={s.porkArrEnd} onChange={(e) => s.setPorkArrEnd(e.target.value)} className="input" />
            </div>
          </div>
          <button onClick={computePorkchop} className="btn btn-full" disabled={s.porkchopLoading} style={{ marginTop: '6px' }}>
            {s.porkchopLoading ? 'Regenerating...' : 'Regenerate'}
          </button>
          {s.porkchop?.optimal && (
            <div className="hint" style={{ color: 'var(--cyan)' }}>
              Optimal: {s.porkchop.optimal.dv_total.toFixed(3)} km/s ({Math.round(s.porkchop.optimal.tof_days)}d)
            </div>
          )}
        </div>
      )}

      {/* NEA targets */}
      <div className="panel">
        <div className="panel-header"><div className="panel-header-dot" />NEA Targets</div>
        <div className="row">
          <div className="flex-1">
            <div className="field-label">Max Δv</div>
            <select value={s.maxDvFilter} onChange={(e) => s.setMaxDvFilter(Number(e.target.value))} className="input">
              {[4, 5, 6, 7, 8, 10, 12].map(v => <option key={v} value={v}>{v} km/s</option>)}
            </select>
          </div>
          <button onClick={loadTargets} className="btn btn-sm btn-ghost" style={{ alignSelf: 'flex-end' }} disabled={s.targetsLoading}>
            {s.targetsLoading ? '...' : 'Load'}
          </button>
        </div>
        {s.targets.length > 0 && (
          <div className="hint">{s.targets.length} accessible targets (NHATS)</div>
        )}
      </div>

      {/* Selected NEA target detail */}
      {s.selectedTarget && (
        <div className="panel" style={{ borderLeftColor: 'var(--cyan)', borderLeftWidth: '2px' }}>
          <div className="panel-header">
            <div className="panel-header-dot" />
            <span style={{ color: 'var(--cyan)' }}>{s.selectedTarget.des}</span>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', lineHeight: 1.8, color: 'var(--text-secondary)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Min Δv</span>
              <span style={{ color: 'var(--cyan)' }}>{s.selectedTarget.min_dv.toFixed(3)} km/s</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Duration</span>
              <span>{s.selectedTarget.min_dv_dur} days</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Size</span>
              <span>{s.selectedTarget.min_size_m > 0 ? `${s.selectedTarget.min_size_m}–${s.selectedTarget.max_size_m} m` : 'Unknown'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>H mag</span>
              <span>{s.selectedTarget.h.toFixed(1)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Trajectories</span>
              <span>{s.selectedTarget.n_via.toLocaleString()}</span>
            </div>
          </div>
          <div className="row" style={{ marginTop: '8px' }}>
            <button
              className="btn flex-1"
              disabled={s.porkchopLoading}
              onClick={async () => {
                const target = useStore.getState().selectedTarget;
                if (!target) return;
                s.setError(null);
                s.setPorkchopLoading(true);
                s.setReferenceMission(null);
                try {
                  // Search window: 2 years from epoch
                  const epoch = useStore.getState().epoch;
                  const depStart = epoch;
                  const depEnd = new Date(new Date(epoch).getTime() + 730 * 86400000).toISOString().slice(0, 10);
                  const arrStart = new Date(new Date(epoch).getTime() + 60 * 86400000).toISOString().slice(0, 10);
                  const arrEnd = new Date(new Date(epoch).getTime() + 1095 * 86400000).toISOString().slice(0, 10);
                  const result = await getNeaPorkchop(target.des, depStart, depEnd, arrStart, arrEnd, 40);
                  s.setPorkchop(result);
                  s.setViewMode('porkchop');
                } catch (e) { s.setError(String(e)); }
                finally { s.setPorkchopLoading(false); }
              }}
            >
              {s.porkchopLoading ? '...' : 'Plan Mission'}
            </button>
            <button onClick={() => s.setSelectedTarget(null)} className="btn btn-ghost btn-sm" style={{ fontSize: '9px' }}>
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Mission Library — unified Historic / Benchmark / Designed with propulsion filter */}
      <div className="panel">
        <button
          onClick={() => setLibExpanded(!libExpanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
            background: 'none', border: 'none', cursor: 'pointer', padding: 0,
            marginBottom: libExpanded ? '10px' : 0,
          }}
        >
          <div className="panel-header-dot" style={{ background: CATEGORY_META[libCategory].accent }} />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 600,
            letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--text-dim)',
          }}>
            Mission Library
          </span>
          <span style={{
            marginLeft: 'auto',
            fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)',
          }}>
            {filteredMissions.length}
          </span>
          <span style={{
            fontSize: '8px', color: 'var(--text-dim)', marginLeft: '6px',
            transform: libExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s',
          }}>▶</span>
        </button>
        {libExpanded && (
          <>
            {/* Category tabs */}
            <div style={{ display: 'flex', gap: '4px', marginBottom: '6px' }}>
              {(Object.keys(CATEGORY_META) as MissionCategory[]).map(c => (
                <button
                  key={c}
                  onClick={() => { setLibCategory(c); setLibPropulsion('all'); }}
                  style={{
                    flex: 1,
                    padding: '5px 6px',
                    background: libCategory === c ? CATEGORY_META[c].accent : 'var(--void)',
                    color: libCategory === c ? '#000' : 'var(--text-secondary)',
                    border: '1px solid var(--panel-border)',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '9px',
                    fontWeight: libCategory === c ? 700 : 400,
                    letterSpacing: '0.5px',
                    textTransform: 'uppercase',
                  }}
                >
                  {CATEGORY_META[c].label}
                  <span style={{ marginLeft: '4px', opacity: 0.7 }}>{categoryCounts[c]}</span>
                </button>
              ))}
            </div>

            {/* Category hint */}
            <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: '6px' }}>
              {CATEGORY_META[libCategory].hint}
            </div>

            {/* Propulsion chips — only show if more than one type in current category */}
            {availablePropulsions.length > 1 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
                <button onClick={() => setLibPropulsion('all')} style={chipStyle(libPropulsion === 'all')}>
                  All
                </button>
                {availablePropulsions.map(p => (
                  <button key={p} onClick={() => setLibPropulsion(p)} style={chipStyle(libPropulsion === p)}>
                    {PROPULSION_META[p].label}
                  </button>
                ))}
              </div>
            )}

            {/* Mission list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {filteredMissions.length === 0 ? (
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', fontStyle: 'italic', padding: '8px' }}>
                  No missions match filter.
                </div>
              ) : filteredMissions.map(m => {
                const key = `${m.category}:${m.id}`;
                const isLoading = missionLoading === key;
                return (
                  <button
                    key={key}
                    disabled={missionLoading !== null}
                    onClick={() => loadMission(m)}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '8px 10px', background: 'var(--void)', border: '1px solid var(--panel-border)',
                      borderLeft: `3px solid ${PROPULSION_META[m.propulsion].accent}`,
                      borderRadius: '3px', cursor: 'pointer', textAlign: 'left',
                      opacity: missionLoading && !isLoading ? 0.5 : 1,
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0, flex: 1 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-primary)' }}>
                        {isLoading ? <AnimatedDots text={CATEGORY_META[m.category].verb} /> : m.label}
                      </span>
                      {m.detail && (
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-dim)' }}>
                          {m.detail}
                        </span>
                      )}
                    </div>
                    <span style={{
                      fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)',
                      letterSpacing: '0.3px', textAlign: 'right', marginLeft: '8px',
                      maxWidth: '38%',
                    }}>
                      {m.sub}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Error */}
      {s.error && (
        <div className="error-box">
          {s.error}
          <button onClick={() => s.setError(null)} style={{
            float: 'right', background: 'none', border: 'none',
            color: 'var(--red)', cursor: 'pointer', fontSize: '10px',
          }}>✕</button>
        </div>
      )}
    </div>
  );
}

function AnimatedDots({ text }: { text: string }) {
  const [dots, setDots] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setDots(d => (d + 1) % 4), 400);
    return () => clearInterval(id);
  }, []);
  return <>{text}{'.'.repeat(dots)}</>
}
