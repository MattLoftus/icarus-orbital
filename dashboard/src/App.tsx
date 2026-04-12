import { useEffect } from 'react';
import { SolarSystem } from './components/SolarSystem';
import { PorkchopPlot } from './components/PorkchopPlot';
import { TargetsView } from './components/TargetsView';
import { Guide } from './components/Guide';
import { Sidebar } from './components/Sidebar';
import { useStore } from './store/store';
import { getPlanets, getOrbit } from './lib/api';
import { suggestWindow } from './lib/windows';
import type { ViewMode } from './store/store';
import './index.css';

function TopBar() {
  const { viewMode, setViewMode, epoch, planets, transfer, referenceMission } = useStore();

  const tabs: { mode: ViewMode; label: string }[] = [
    { mode: 'solar-system', label: 'Mission Planner' },
    { mode: 'porkchop', label: 'Porkchop Analysis' },
    { mode: 'targets', label: 'NEA Database' },
    { mode: 'guide', label: 'Guide' },
  ];

  return (
    <div className="top-bar">
      <div className="top-bar-title" style={{ cursor: 'pointer' }} onClick={() => setViewMode('solar-system')}>I.C.A.R.U.S.</div>
      <div className="top-bar-sep" />
      <div className="top-bar-nav">
        {tabs.map(({ mode, label }) => (
          <button
            key={mode}
            className={`nav-tab ${viewMode === mode ? 'nav-tab-active' : ''}`}
            onClick={() => setViewMode(mode)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="top-bar-status">
        {referenceMission ? (
          <span style={{ color: 'var(--amber)' }}>{referenceMission.name}</span>
        ) : transfer ? (
          <>
            <span>{transfer.departure_body} → {transfer.arrival_body}</span>
            <span style={{ color: 'var(--cyan)' }}>{transfer.dv_total.toFixed(2)} km/s</span>
            <span>{Math.round(transfer.tof_days)}d</span>
          </>
        ) : null}
        <div className="top-bar-sep" />
        <span>EPOCH {epoch}</span>
        <div className="status-dot" />
        <span>{planets.length > 0 ? 'ONLINE' : 'OFFLINE'}</span>
      </div>
    </div>
  );
}

function HUD() {
  const { transfer, referenceMission, animationProgress, porkchopLoading, transferLoading } = useStore();

  // For regular transfers, show stats
  const showStats = transfer && transfer.dv_total > 0;

  return (
    <>
      {/* Transfer stats HUD — bottom right of 3D view */}
      {showStats && (
        <div className="hud-overlay hud-bottom-right">
          <div className="hud-stat">
            <div className="hud-stat-label">Total Δv</div>
            <div className="hud-stat-value">{transfer.dv_total.toFixed(3)}<span className="hud-stat-unit">km/s</span></div>
          </div>
          <div className="hud-stat">
            <div className="hud-stat-label">C3 Launch</div>
            <div className="hud-stat-value">{transfer.c3_launch.toFixed(1)}<span className="hud-stat-unit">km²/s²</span></div>
          </div>
          <div className="hud-stat">
            <div className="hud-stat-label">Time of Flight</div>
            <div className="hud-stat-value">{Math.round(transfer.tof_days)}<span className="hud-stat-unit">days</span></div>
          </div>
          <div className="hud-stat">
            <div className="hud-stat-label">V∞ Arrival</div>
            <div className="hud-stat-value">{transfer.v_inf_arrival.toFixed(3)}<span className="hud-stat-unit">km/s</span></div>
          </div>
        </div>
      )}

      {/* Reference mission timeline — bottom right */}
      {referenceMission && (
        <div className="hud-overlay" style={{
          bottom: '60px', right: '12px',
          background: 'rgba(6,10,18,0.9)', border: '1px solid var(--panel-border)',
          borderRadius: '4px', padding: '12px 16px', backdropFilter: 'blur(8px)',
          minWidth: '280px', pointerEvents: 'auto',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 600,
            color: 'var(--cyan)', marginBottom: '8px', letterSpacing: '0.5px',
          }}>
            {referenceMission.name}
          </div>
          {referenceMission.events?.map((ev: any, i: number) => {
            // Determine if this event has been "reached" based on animation progress
            const totalEvents = referenceMission.events.length;
            const eventProgress = i / (totalEvents - 1);
            const reached = animationProgress >= eventProgress;
            const active = Math.abs(animationProgress - eventProgress) < 0.05;

            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '4px 0',
                opacity: reached ? 1 : 0.35,
              }}>
                <div style={{
                  width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
                  background: active ? 'var(--cyan-bright)' :
                    ev.type === 'launch' ? 'var(--cyan)' :
                    ev.type === 'arrival' ? 'var(--amber)' : 'var(--text-secondary)',
                  boxShadow: active ? '0 0 6px var(--cyan)' : 'none',
                }} />
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: '10px',
                  color: active ? 'var(--cyan)' : 'var(--text-secondary)',
                  flex: 1,
                }}>
                  {ev.body}
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: '9px',
                  color: 'var(--text-dim)',
                }}>
                  {ev.date}
                </span>
                {ev.type === 'flyby' && ev.dv_gained_km_s > 0 && (
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: '9px',
                    color: 'var(--green)',
                  }}>
                    +{ev.dv_gained_km_s}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Loading overlay */}
      {(porkchopLoading || transferLoading) && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(6, 10, 18, 0.6)',
          zIndex: 10,
        }}>
          <div style={{ textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto 8px' }} />
            <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', fontSize: '10px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              {porkchopLoading ? 'Generating porkchop analysis...' : 'Computing trajectory...'}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MainView() {
  const { viewMode } = useStore();

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
      {viewMode === 'solar-system' && <SolarSystem />}
      {viewMode === 'porkchop' && <PorkchopPlot />}
      {viewMode === 'targets' && <TargetsView />}
      {viewMode === 'guide' && <Guide />}
      {viewMode === 'solar-system' && <HUD />}
    </div>
  );
}

function App() {
  const { initialized, setInitialized, setPlanets, setOrbit, setError } = useStore();

  useEffect(() => {
    if (initialized) return;
    setInitialized(true);

    // Compute initial transfer dates from phase angle geometry
    const w = suggestWindow('earth', 'mars', '2026-03-15');
    useStore.setState({
      departureDate: w.depDate,
      arrivalDate: w.arrDate,
      porkDepStart: w.depStart,
      porkDepEnd: w.depEnd,
      porkArrStart: w.arrStart,
      porkArrEnd: w.arrEnd,
    });

    (async () => {
      try {
        const planets = await getPlanets('2026-03-15');
        setPlanets(planets);
        const orbitBodies = ['mercury', 'venus', 'earth', 'mars', 'ceres', 'vesta',
          'jupiter', 'saturn', 'uranus', 'neptune', 'pluto', 'eris', 'haumea', 'makemake'];
        for (const body of orbitBodies) {
          getOrbit(body, '2026-01-01').then(orbit => setOrbit(body, orbit)).catch(() => {});
        }
      } catch (e) {
        setError(`Failed to load: ${e}`);
      }
    })();
  }, [initialized, setInitialized, setPlanets, setOrbit, setError]);

  const { viewMode: currentView } = useStore();
  const showSidebar = currentView !== 'guide';

  return (
    <div className="app-layout">
      <TopBar />
      <div className="main-area">
        {showSidebar && <Sidebar />}
        <MainView />
      </div>
    </div>
  );
}

export default App;
