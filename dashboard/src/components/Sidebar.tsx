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

const REF_MISSIONS = [
  { id: 'voyager', label: 'Voyager 2', sub: 'E→J→S→U→N' },
  { id: 'cassini', label: 'Cassini', sub: 'E→V→V→E→J→S' },
  { id: 'new horizons', label: 'New Horizons', sub: 'E→J→Pluto' },
  { id: 'galileo', label: 'Galileo', sub: 'E→V→E→E→J' },
  { id: 'mariner', label: 'Mariner 10', sub: 'E→V→Mercury' },
  { id: 'juno', label: 'Juno', sub: 'E→E→J' },
  { id: 'pioneer', label: 'Pioneer 10', sub: 'E→J' },
  { id: 'messenger', label: 'MESSENGER', sub: 'E→E→V→V→M→M→M→M' },
];

const HISTORICAL_EP_MISSIONS = [
  { id: 'dawn', label: 'Dawn', sub: 'E→M→Vesta→Ceres · Ion', detail: '2007-2018 · NASA' },
  { id: 'hayabusa2', label: 'Hayabusa2', sub: 'E→Ryugu→E · Ion sample return', detail: '2014-2020 · JAXA' },
  { id: 'hayabusa', label: 'Hayabusa', sub: 'E→Itokawa→E · Ion sample return', detail: '2003-2010 · JAXA' },
  { id: 'bepicolombo', label: 'BepiColombo', sub: '9 GAs → Mercury · Hybrid', detail: '2018-2025 · ESA/JAXA' },
  { id: 'psyche', label: 'Psyche', sub: 'E→M→Psyche · Ion (Hall)', detail: '2023-2029 · NASA' },
  { id: 'ikaros', label: 'IKAROS', sub: 'E→Venus · Solar sail', detail: '2010 · JAXA' },
];

export function Sidebar() {
  const s = useStore();
  const [refLoading, setRefLoading] = useState<string | null>(null);
  const [gtopLoading, setGtopLoading] = useState<string | null>(null);
  const [designedLoading, setDesignedLoading] = useState<string | null>(null);
  const [histEpLoading, setHistEpLoading] = useState<string | null>(null);
  const [windowsExpanded, setWindowsExpanded] = useState(false);
  const [refExpanded, setRefExpanded] = useState(false);
  const [gtopExpanded, setGtopExpanded] = useState(false);
  const [designedExpanded, setDesignedExpanded] = useState(false);
  const [histEpExpanded, setHistEpExpanded] = useState(false);

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

  return (
    <div className="sidebar">
      {/* Epoch */}
      <div className="panel">
        <div className="panel-header"><div className="panel-header-dot" />Epoch</div>
        <div className="row">
          <input type="date" value={s.epoch} onChange={(e) => s.setEpoch(e.target.value)} className="input flex-1" />
          <button onClick={loadPlanets} className="btn btn-sm btn-ghost">
            {s.planets.length > 0 ? 'Reload' : 'Load'}
          </button>
        </div>
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

      {/* Reference Missions — collapsible */}
      <div className="panel">
        <button
          onClick={() => setRefExpanded(!refExpanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
            background: 'none', border: 'none', cursor: 'pointer', padding: 0,
            marginBottom: refExpanded ? '10px' : 0,
          }}
        >
          <div className="panel-header-dot" style={{ background: 'var(--amber)' }} />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 600,
            letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--text-dim)',
          }}>
            Reference Missions
          </span>
          <span style={{
            marginLeft: 'auto', fontSize: '8px', color: 'var(--text-dim)',
            transform: refExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s',
          }}>▶</span>
        </button>
        {refExpanded && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {REF_MISSIONS.map(m => (
              <button
                key={m.id}
                disabled={refLoading === m.id}
                onClick={async () => {
                  setRefLoading(m.id);
                  try {
                    const mission = await getReferenceMission(m.id);
                    const launchDate = mission.events[0]?.date || '';
                    // Immediately set approximate planet positions for the mission epoch
                    const approx = allPlanetPositionsAtDate(launchDate);
                    const approxPlanets: PlanetState[] = Object.entries(approx).map(([name, position]) => ({
                      name, position, velocity: [0, 0, 0] as [number, number, number],
                      distance_au: Math.sqrt(position[0] ** 2 + position[1] ** 2 + position[2] ** 2) / 1.496e8,
                      speed_kms: 0,
                    }));
                    const stateUpdate: Record<string, any> = {
                      planets: approxPlanets,
                      transfer: {
                        departure_body: mission.sequence[0],
                        arrival_body: mission.sequence[mission.sequence.length - 1],
                        departure_utc: launchDate,
                        arrival_utc: mission.events[mission.events.length - 1]?.date || '',
                        tof_days: 0,
                        dv_departure: 0, dv_arrival: 0, dv_total: 0,
                        c3_launch: 0, v_inf_arrival: 0,
                        trajectory_positions: mission.trajectory_positions,
                      },
                      referenceMission: mission,
                      viewMode: 'solar-system',
                      animationProgress: 0,
                      animationPlaying: false,
                      epoch: launchDate,
                    };
                    useStore.setState(stateUpdate);
                    // Refine with precise positions from API (non-blocking)
                    getPlanets(launchDate).then(p => s.setPlanets(p)).catch(() => {});
                    for (const body of ['mercury', 'venus', 'earth', 'mars', 'ceres', 'vesta',
                      'jupiter', 'saturn', 'uranus', 'neptune', 'pluto', 'eris', 'haumea', 'makemake']) {
                      getOrbit(body, launchDate).then(orbit => s.setOrbit(body, orbit)).catch(() => {});
                    }
                  } catch (e) { s.setError(String(e)); }
                  finally { setRefLoading(null); }
                }}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 10px', background: 'var(--void)', border: '1px solid var(--panel-border)',
                  borderRadius: '3px', cursor: 'pointer', textAlign: 'left',
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-primary)' }}>
                  {refLoading === m.id ? 'Loading...' : m.label}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)', letterSpacing: '0.3px' }}>
                  {m.sub}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Historical Electric Propulsion Missions — collapsible */}
      <div className="panel">
        <button
          onClick={() => setHistEpExpanded(!histEpExpanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
            background: 'none', border: 'none', cursor: 'pointer', padding: 0,
            marginBottom: histEpExpanded ? '10px' : 0,
          }}
        >
          <div className="panel-header-dot" style={{ background: '#00d4e0' }} />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 600,
            letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--text-dim)',
          }}>
            Ion / Sail Reference Missions
          </span>
          <span style={{
            marginLeft: 'auto', fontSize: '8px', color: 'var(--text-dim)',
            transform: histEpExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s',
          }}>▶</span>
        </button>
        {histEpExpanded && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: '4px' }}>
              Historical missions with electric, hybrid, or sail propulsion (first click ~30-120s)
            </div>
            {HISTORICAL_EP_MISSIONS.map(m => (
              <button
                key={m.id}
                disabled={histEpLoading !== null}
                onClick={async () => {
                  setHistEpLoading(m.id);
                  try {
                    const mission = await getReferenceMission(m.id);
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
                        dv_departure: 0, dv_arrival: 0, dv_total: 0,
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
                  finally { setHistEpLoading(null); }
                }}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 10px', background: 'var(--void)', border: '1px solid var(--panel-border)',
                  borderRadius: '3px', cursor: 'pointer', textAlign: 'left',
                  opacity: histEpLoading && histEpLoading !== m.id ? 0.5 : 1,
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-primary)' }}>
                    {histEpLoading === m.id ? <AnimatedDots text="Building" /> : m.label}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-dim)' }}>
                    {m.detail}
                  </span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)', letterSpacing: '0.3px' }}>
                  {m.sub}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* GTOP Benchmarks — collapsible */}
      <div className="panel">
        <button
          onClick={() => setGtopExpanded(!gtopExpanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
            background: 'none', border: 'none', cursor: 'pointer', padding: 0,
            marginBottom: gtopExpanded ? '10px' : 0,
          }}
        >
          <div className="panel-header-dot" style={{ background: 'var(--green)' }} />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 600,
            letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--text-dim)',
          }}>
            GTOP Benchmarks
          </span>
          <span style={{
            marginLeft: 'auto', fontSize: '8px', color: 'var(--text-dim)',
            transform: gtopExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s',
          }}>▶</span>
        </button>
        {gtopExpanded && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: '4px' }}>
              Optimized trajectories computed on-demand (~30-60s)
            </div>
            {[
              { id: 'cassini2', label: 'Cassini2', sub: 'E→V→V→E→J→S', pub: '8.383' },
              { id: 'messenger', label: 'Messenger', sub: 'E→E→V→V→Me', pub: '8.630' },
              { id: 'rosetta', label: 'Rosetta', sub: 'E→E→Ma→E→E→67P', pub: '1.343' },
            ].map(m => (
              <button
                key={m.id}
                disabled={gtopLoading !== null}
                onClick={async () => {
                  setGtopLoading(m.id);
                  try {
                    const mission = await getGTOPBenchmark(m.id);
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
                        dv_departure: 0, dv_arrival: 0, dv_total: mission.stats?.total_dv_km_s || 0,
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
                  finally { setGtopLoading(null); }
                }}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 10px', background: 'var(--void)', border: '1px solid var(--panel-border)',
                  borderRadius: '3px', cursor: 'pointer', textAlign: 'left',
                  opacity: gtopLoading && gtopLoading !== m.id ? 0.5 : 1,
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-primary)' }}>
                    {gtopLoading === m.id ? <AnimatedDots text="Optimizing" /> : m.label}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-dim)' }}>
                    Best: {m.pub} km/s
                  </span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)', letterSpacing: '0.3px' }}>
                  {m.sub}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Designed Missions — collapsible */}
      <div className="panel">
        <button
          onClick={() => setDesignedExpanded(!designedExpanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px', width: '100%',
            background: 'none', border: 'none', cursor: 'pointer', padding: 0,
            marginBottom: designedExpanded ? '10px' : 0,
          }}
        >
          <div className="panel-header-dot" style={{ background: '#8b5cf6' }} />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 600,
            letterSpacing: '1.2px', textTransform: 'uppercase', color: 'var(--text-dim)',
          }}>
            Designed Missions
          </span>
          <span style={{
            marginLeft: 'auto', fontSize: '8px', color: 'var(--text-dim)',
            transform: designedExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s',
          }}>▶</span>
        </button>
        {designedExpanded && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ fontSize: '9px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: '4px' }}>
              Novel trajectories optimized by I.C.A.R.U.S.
            </div>
            {[
              { id: 'grand-tour-eejs', label: 'Grand Tour: EEJS', sub: 'E→E→J→S', detail: '8.80 km/s · 13.4yr' },
              { id: 'grand-tour-vejs', label: 'Grand Tour: VEJS', sub: 'E→V→E→J→S', detail: '9.04 km/s · 12.2yr' },
              { id: 'fast-jupiter-vej', label: 'Jupiter: VEJ', sub: 'E→V→E→J', detail: '10.18 km/s · 4.6yr' },
              { id: 'jupiter-emaj', label: 'Jupiter: EMaJ', sub: 'E→E→Ma→J', detail: '10.07 km/s · 6.0yr' },
              { id: 'jupiter-maej', label: 'Jupiter: MaEJ', sub: 'E→Ma→E→J', detail: '10.66 km/s · 6.5yr' },
              { id: 'sample-return-sg344', label: 'Sample Return: SG344', sub: 'E→2000 SG344→E', detail: '1.83 km/s · 2.1yr' },
              { id: 'sample-return-hu4', label: 'Sample Return: HU4', sub: 'E→2008 HU4→E', detail: '3.92 km/s · 1.9yr' },
              { id: 'sample-return-ao10', label: 'Sample Return: AO10', sub: 'E→1999 AO10→E', detail: '5.91 km/s · 1.6yr' },
              { id: 'interstellar-vej', label: 'Interstellar: VEJ', sub: 'E→V→E→J→∞', detail: '7.40 AU/yr · 200AU in 27yr' },
              { id: 'tour-sg344-rh120', label: 'Tour: SG344→RH120', sub: 'E→SG344→RH120→E', detail: '3.71 km/s · 2.5yr' },
              { id: 'lt-earth-mars', label: 'Low-Thrust: Earth→Mars', sub: 'Ion, E→Mars', detail: '223 kg Xe · 400d · 4.71 km/s' },
              { id: 'lt-earth-vesta', label: 'Low-Thrust: Earth→Vesta', sub: 'Ion, Dawn-like', detail: '350 kg Xe · 1300d · 9.18 km/s' },
              { id: 'sail-interstellar', label: 'Solar Sail: Interstellar', sub: 'Zero propellant', detail: '15.5 km/s · 3.3 AU/yr' },
              { id: 'hybrid-mars-capture', label: 'Hybrid: Mars Capture', sub: 'Ion + Chemical orbit insertion', detail: 'Ion cruise + chem capture' },
            ].map(m => (
              <button
                key={m.id}
                disabled={designedLoading !== null}
                onClick={async () => {
                  setDesignedLoading(m.id);
                  try {
                    const mission = await getDesignedMission(m.id);
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
                        dv_departure: 0, dv_arrival: 0, dv_total: mission.stats?.total_dv_km_s || 0,
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
                  finally { setDesignedLoading(null); }
                }}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 10px', background: 'var(--void)', border: '1px solid var(--panel-border)',
                  borderRadius: '3px', cursor: 'pointer', textAlign: 'left',
                  opacity: designedLoading && designedLoading !== m.id ? 0.5 : 1,
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-primary)' }}>
                    {designedLoading === m.id ? <AnimatedDots text="Loading" /> : m.label}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-dim)' }}>
                    {m.detail}
                  </span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-dim)', letterSpacing: '0.3px' }}>
                  {m.sub}
                </span>
              </button>
            ))}
          </div>
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
