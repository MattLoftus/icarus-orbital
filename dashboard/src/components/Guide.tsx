export function Guide() {
  return (
    <div style={{
      width: '100%', height: '100%', overflowY: 'auto',
      padding: '32px 48px', maxWidth: '960px', margin: '0 auto',
      fontFamily: 'var(--font-sans)', color: 'var(--text-primary)',
    }}>
      <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--cyan)', fontFamily: 'var(--font-mono)', letterSpacing: '1px', marginBottom: '4px' }}>
        I.C.A.R.U.S. Guide
      </h1>
      <p style={{ color: 'var(--text-dim)', fontSize: '13px', marginBottom: '32px' }}>
        Interplanetary Computation and Route Utility System — an interactive mission designer with real NASA data.
      </p>

      {/* Overview */}
      <Section title="Overview">
        <p>
          I.C.A.R.U.S. computes fuel-optimal transfer trajectories between solar system bodies using Lambert's problem,
          the fundamental building block of all interplanetary mission design. It connects to real NASA ephemeris data
          (JPL SPICE) and the NHATS near-Earth asteroid database to produce physically accurate results.
        </p>
        <Grid cols={3}>
          <Card accent="var(--cyan)" title="Lambert Solver">
            Given two positions and a time-of-flight, find the orbit connecting them. Every transfer trajectory
            is a Lambert solution. The solver runs at ~4,300 solutions/sec.
          </Card>
          <Card accent="var(--amber)" title="Porkchop Analysis">
            A grid of Lambert solutions over departure × arrival date windows. The characteristic "porkchop" contour
            reveals optimal launch windows — the valleys where delta-v is minimized.
          </Card>
          <Card accent="var(--green)" title="Real Ephemeris">
            Planet positions come from NASA's SPICE toolkit (DE440S ephemeris), accurate to sub-kilometer precision.
            NEA targets from the NHATS database represent real mission-accessible asteroids.
          </Card>
        </Grid>
      </Section>

      {/* Key Concepts */}
      <Section title="Key Concepts">
        <Grid cols={2}>
          <Card accent="var(--cyan)" title="Delta-v (Δv)">
            The total velocity change a spacecraft needs — the fundamental "currency" of spaceflight.
            Lower Δv means less fuel, smaller rockets, and cheaper missions. A typical Earth–Mars transfer
            requires 5–7 km/s total. Earth–Jupiter requires 8–15 km/s.
          </Card>
          <Card accent="var(--cyan)" title="C3 (Launch Energy)">
            C3 = v<sub>∞</sub><sup>2</sup> at departure — the hyperbolic excess energy the launch vehicle
            must provide. Measured in km²/s². A C3 of 10 km²/s² is a modest launch; 50+ is aggressive.
            C3 determines which rockets can fly the mission.
          </Card>
          <Card accent="var(--amber)" title="Transfer Windows">
            Optimal launch dates are governed by the synodic period — how often two planets align
            favorably. Earth–Mars windows open every ~26 months. Earth–Jupiter every ~13 months.
            Missing a window means waiting for the next one.
          </Card>
          <Card accent="var(--amber)" title="Time of Flight (TOF)">
            How long the transfer takes. A Hohmann transfer (minimum-energy) to Mars takes ~259 days;
            to Jupiter ~998 days. Shorter TOF costs more Δv. The porkchop plot shows this tradeoff directly.
          </Card>
          <Card accent="var(--green)" title="Gravity Assists">
            A spacecraft flying past a planet can change direction "for free" in the heliocentric frame.
            The deflection angle depends on closest approach distance and v<sub>∞</sub>. Jupiter can
            provide 10+ km/s of free Δv — essential for outer solar system missions.
          </Card>
          <Card accent="var(--green)" title="Hohmann Transfer">
            The minimum-energy two-impulse transfer between circular orbits. Uses half an ellipse tangent
            to both orbits. TOF = √(a<sub>transfer</sub>³) / 2 years. Not always optimal when gravity
            assists or non-circular orbits are involved.
          </Card>
          <Card accent="#8b5cf6" title="Low-Thrust Propulsion">
            Electric propulsion (ion engines, Hall thrusters) produces tiny thrust (millinewtons) but
            very high I<sub>sp</sub> (3000+ seconds vs 300 for chemical). The Sims-Flanagan method
            discretizes the trajectory into segments with bounded impulses, solving the resulting NLP
            to find optimal thrust profiles. Requires longer TOF but dramatically less propellant.
          </Card>
        </Grid>
      </Section>

      {/* How It Works */}
      <Section title="How It Works">
        <Grid cols={4}>
          <StepCard n={1} title="Select Bodies">
            Choose departure and arrival bodies. The app computes the next optimal launch window
            from phase angle geometry and sets default dates.
          </StepCard>
          <StepCard n={2} title="Compute Transfer">
            A Lambert solver finds the transfer orbit connecting the two bodies at the specified dates.
            The trajectory is propagated via Kepler's equation for visualization.
          </StepCard>
          <StepCard n={3} title="Porkchop Analysis">
            Generate a grid of 3,600 Lambert solutions (60×60) across the search window. The heatmap
            reveals all viable launch opportunities and their delta-v cost.
          </StepCard>
          <StepCard n={4} title="Iterate">
            Click on the porkchop plot to select dates, adjust parameters, compare trajectories.
            The animation scrubber shows the spacecraft's progress along the arc.
          </StepCard>
        </Grid>
      </Section>

      {/* Reading the Dashboard */}
      <Section title="Reading the Dashboard">
        <Grid cols={2}>
          <Card accent="var(--cyan)" title="3D Solar System">
            The main view shows planet positions from SPICE ephemeris data at the selected epoch.
            Orbit paths show one full orbital period. The transfer arc (teal) shows the computed
            trajectory with departure (teal dot) and arrival (amber dot) markers. Flyby encounters
            are marked with body-colored rings. Use the camera presets (top-left) to switch between
            perspective, ecliptic top-down, and inner/outer views. Planet focus buttons (top-right)
            snap the camera to a specific body.
          </Card>
          <Card accent="var(--amber)" title="Porkchop Plot">
            X-axis is arrival date, Y-axis is departure date. Color encodes total Δv — dark blue/teal
            is low (good), yellow is high (expensive). The crosshair marks the global optimum. Click
            anywhere to select that date combination — the transfer is auto-computed and displayed in the 3D view.
          </Card>
          <Card accent="var(--green)" title="HUD Stats">
            Bottom-right of the 3D view shows the current transfer's key metrics: total Δv, C3 launch
            energy, time of flight, and arrival v<sub>∞</sub>. These update when you compute a new transfer.
          </Card>
          <Card accent="#8b5cf6" title="NEA Database">
            Lists accessible near-Earth asteroids from NASA's NHATS study. Sorted by minimum Δv.
            681 targets are reachable with less than 6 km/s. Each entry shows estimated size,
            absolute magnitude (H), and the number of viable trajectory windows.
          </Card>
        </Grid>
      </Section>

      {/* Reference Missions */}
      <Section title="Reference Missions">
        <p style={{ marginBottom: '12px' }}>
          Eight historic missions are available for visualization with animated playback, event timelines,
          and flyby markers. Planets move to their correct positions at each date during playback.
        </p>
        <Grid cols={2}>
          <Card accent="var(--cyan)" title="Voyager 2 Grand Tour (1977–1989)">
            Earth → Jupiter → Saturn → Uranus → Neptune. The only spacecraft to visit all four
            outer planets, enabled by a rare alignment that occurs once every 175 years.
            Jupiter's gravity assist provided ~10 km/s.
          </Card>
          <Card accent="var(--amber)" title="Cassini VVEJGA (1997–2004)">
            Earth → Venus → Venus → Earth → Jupiter → Saturn. Four gravity assists over 7 years
            to reach Saturn. The double Venus flyby built up enough energy to reach Jupiter's orbit.
          </Card>
          <Card accent="var(--green)" title="New Horizons (2006–2015)">
            Earth → Jupiter → Pluto. The fastest spacecraft ever launched, reaching Jupiter in 13 months
            for a gravity assist, then continuing 8 more years to Pluto.
          </Card>
          <Card accent="#8b5cf6" title="MESSENGER (2004–2011)">
            Earth → Earth → Venus → Venus → Mercury × 3 → Mercury orbit. Six gravity assists over 7 years
            to slow down enough for Mercury orbit — reaching Mercury requires more Δv than leaving the solar system.
          </Card>
        </Grid>
        <p style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-dim)' }}>
          Also available: Galileo VEEGA, Mariner 10, Juno, Pioneer 10.
        </p>
      </Section>

      {/* Data Sources */}
      <Section title="Data Sources">
        <Grid cols={2}>
          <Card accent="var(--text-dim)" title="JPL SPICE (DE440S)">
            Planet ephemeris from NASA's Navigation and Ancillary Information Facility. The DE440S
            kernel covers 1849–2150 with sub-kilometer accuracy for all major planets. Accessed
            via SpiceyPy (Python bindings for the SPICE toolkit).
          </Card>
          <Card accent="var(--text-dim)" title="NASA NHATS">
            Near-Earth Object Human Space Flight Accessible Targets Study. A continuously updated
            database of asteroids accessible with current or near-future propulsion. Queried via
            the JPL SSD API (no authentication required).
          </Card>
        </Grid>
      </Section>

      {/* Technical Stack */}
      <Section title="Technical Stack">
        <Grid cols={2}>
          <Card accent="var(--cyan)" title="Backend (Python)">
            <TechList items={[
              'Custom Lambert solver (universal variable + Stumpff functions)',
              'Patched conics gravity assist model',
              'Keplerian orbit propagation',
              'MGA-1DSM optimizer (multi-restart differential evolution)',
              'Sims-Flanagan low-thrust trajectory optimizer',
              'NEA transfers via Keplerian propagation from orbital elements',
              'SpiceyPy for SPICE ephemeris (DE440S)',
              'FastAPI REST server with LRU caching',
              '8 reference missions + GTOP Cassini1 benchmark',
            ]} />
          </Card>
          <Card accent="var(--amber)" title="Frontend (React)">
            <TechList items={[
              'React 19 + TypeScript + Vite',
              'react-three-fiber with textured planets + starfield',
              'Canvas-rendered porkchop heatmaps (click-to-select)',
              'Trajectory animation with planet orbital motion',
              'Flyby markers + mission event timeline',
              'Phase-angle-based launch window computation',
              'Zustand state management',
            ]} />
          </Card>
        </Grid>
      </Section>

      <div style={{ height: '48px' }} />
    </div>
  );
}

// --- Reusable sub-components ---

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '28px' }}>
      <h2 style={{
        fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)',
        fontFamily: 'var(--font-mono)', letterSpacing: '0.5px',
        marginBottom: '12px', textTransform: 'uppercase',
        borderBottom: '1px solid var(--panel-border)', paddingBottom: '6px',
      }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function Grid({ cols, children }: { cols: number; children: React.ReactNode }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, 1fr)`,
      gap: '10px',
      marginTop: '8px',
    }}>
      {children}
    </div>
  );
}

function Card({ accent, title, children }: { accent: string; title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--panel-border)',
      borderLeft: `2px solid ${accent}`,
      borderRadius: '4px',
      padding: '12px 14px',
    }}>
      <h3 style={{
        fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)',
        fontFamily: 'var(--font-mono)', marginBottom: '6px',
      }}>
        {title}
      </h3>
      <div style={{ fontSize: '12px', lineHeight: '1.6', color: 'var(--text-secondary)' }}>
        {children}
      </div>
    </div>
  );
}

function StepCard({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--panel-border)',
      borderRadius: '4px',
      padding: '12px 14px',
      position: 'relative',
    }}>
      <div style={{
        position: 'absolute', top: '-8px', left: '12px',
        background: 'var(--cyan)', color: 'var(--void)',
        fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
        width: '18px', height: '18px', borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {n}
      </div>
      <h3 style={{
        fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)',
        fontFamily: 'var(--font-mono)', marginBottom: '6px', marginTop: '4px',
      }}>
        {title}
      </h3>
      <div style={{ fontSize: '11px', lineHeight: '1.6', color: 'var(--text-secondary)' }}>
        {children}
      </div>
    </div>
  );
}

function TechList({ items }: { items: string[] }) {
  return (
    <ul style={{ margin: 0, paddingLeft: '14px', listStyle: 'none' }}>
      {items.map((item, i) => (
        <li key={i} style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '3px' }}>
          <span style={{ color: 'var(--text-dim)', marginRight: '6px' }}>&#x25B8;</span>
          {item}
        </li>
      ))}
    </ul>
  );
}
