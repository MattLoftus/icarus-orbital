import { useState } from 'react';
import { useStore } from '../store/store';
import { getTransfer, getPlanets, getOrbit, getPorkchop, getTargets, getReferenceMission, getNeaPorkchop } from '../lib/api';
import { suggestWindow } from '../lib/windows';
// ReferenceMission type used implicitly via getReferenceMission

const BODIES = ['mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn'];

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

export function Sidebar() {
  const s = useStore();
  const [refLoading, setRefLoading] = useState<string | null>(null);

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

  const loadPlanets = async () => {
    try {
      s.setError(null);
      const planets = await getPlanets(s.epoch);
      s.setPlanets(planets);
      for (const body of ['mercury', 'venus', 'earth', 'mars']) {
        const orbit = await getOrbit(body, s.epoch);
        s.setOrbit(body, orbit);
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

      {/* Reference Missions */}
      <div className="panel">
        <div className="panel-header"><div className="panel-header-dot" style={{ background: 'var(--amber)' }} />Reference Missions</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {REF_MISSIONS.map(m => (
            <button
              key={m.id}
              disabled={refLoading === m.id}
              onClick={async () => {
                setRefLoading(m.id);
                try {
                  const mission = await getReferenceMission(m.id);
                  useStore.setState({
                    transfer: {
                      departure_body: mission.sequence[0],
                      arrival_body: mission.sequence[mission.sequence.length - 1],
                      departure_utc: mission.events[0]?.date || '',
                      arrival_utc: mission.events[mission.events.length - 1]?.date || '',
                      tof_days: 0,
                      dv_departure: 0, dv_arrival: 0, dv_total: 0,
                      c3_launch: 0, v_inf_arrival: 0,
                      v1_transfer: [0, 0, 0], v2_transfer: [0, 0, 0],
                      trajectory_positions: mission.trajectory_positions,
                    } as any,
                    referenceMission: mission,
                    viewMode: 'solar-system',
                    animationProgress: 0,
                    animationPlaying: false,
                  });
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
