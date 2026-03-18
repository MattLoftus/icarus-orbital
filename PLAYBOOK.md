# Orbital Trajectory Optimization — Playbook

Interactive interplanetary mission designer with real NASA data, trajectory optimization, and 3D visualization.

**Dir:** `~/workspace/orbital-mechanics`
**Owner:** Matt Loftus / Cedar Loop LLC

---

## Vision

A web app where users can:
1. Browse 6,800+ accessible near-Earth asteroids (NASA NHATS database)
2. Generate porkchop plots for Earth-to-target transfers
3. Visualize transfer trajectories in an interactive 3D solar system
4. Add gravity assists and watch trajectories update
5. Reproduce and explore famous missions (Voyager, Cassini, OSIRIS-REx)

**Why this matters:** Nothing like this exists on the web. The gap between toy three.js solar system demos and real astrodynamics tools (Python/MATLAB CLI) is enormous. This bridges it with real physics + real NASA data + interactive 3D.

---

## Stack

### Backend (Python 3.9)
- **Custom Lambert solver** — Izzo/universal variable method (~4,300 solves/sec, validated against textbook values)
- **Custom flyby/gravity assist module** — patched conics approximation
- **scipy.optimize** — global optimization (differential_evolution as pygmo substitute)
- **spiceypy** — NASA SPICE bindings for ephemeris data (de440s.bsp)
- **astroquery** — JPL Horizons queries
- **FastAPI** — REST API server
- **numpy / scipy** — numerical computing

> **Note:** pykep/pygmo don't ship macOS wheels for Python 3.9 and require conda. We rolled our own Lambert solver and MGA framework instead — more control, zero dead dependencies.

### Frontend (React)
- **React 19 + TypeScript + Vite 7**
- **react-three-fiber** — 3D solar system, orbit visualization, trajectory animation
- **Zustand** — state management
- **Tailwind CSS 4** — styling
- **Plotly.js or D3** — porkchop plots, delta-v charts

### Data Sources (all free, no auth except noted)
- **NASA NHATS API** — 6,822 accessible NEA targets with delta-v, duration, launch windows
- **JPL Horizons API** — positions/velocities for any solar system body (rate limit: 1 concurrent)
- **SPICE kernels** — `de440s.bsp` for planets, mission-specific SPKs for validation
- **JPL Small-Body Database API** — orbital elements for 40,000+ NEAs
- **ESA GTOP benchmarks** — Cassini, Messenger, Rosetta trajectory problems (built into pykep)

---

## Phases

### Phase 1: Foundation + Validation
Get pykep/pygmo/spiceypy working. Validate against known missions. Prove the math works.

- [x] Python environment setup (spiceypy, scipy, astroquery, FastAPI)
- [x] Download SPICE kernels (de440s.bsp, naif0012.tls, pck00011.tpc)
- [x] Custom Lambert solver (universal variable + Stumpff functions, 4,300 solves/sec)
- [x] Lambert solver validation — Earth-Mars 6.5 km/s, angular momentum conserved to 1e-16
- [x] Porkchop plot generation — Earth-Mars 2026 window, optimal: 5.6 km/s / 314 days
- [x] Gravity assist module — patched conics, validated on Jupiter (128° deflection, 18 km/s free Δv)
- [x] Keplerian orbit propagation (universal variable, Earth closure <0.02% after 1 year, transfer accuracy <2 km)
- [x] Reproduce Voyager 2 Jupiter flyby using real SPICE data (distance match 0.06%, v-inf conserved 0.7%, deflection 5.3° from theory)
- [x] MGA-1DSM optimizer (scipy differential_evolution) — Earth-Mars direct: 5.608 km/s
- [x] MGA optimizer tuned for multi-flyby — multi-restart DE, strategy rotation, proportional penalties. E-V-E-J saves 2.1 km/s over direct (12.3 vs 14.4)
- [x] Reproduce Cassini VVEJGA — 6-body MGA optimization: 11.35 km/s, 7.3yr, departure Nov 1997 (actual: Oct 1997). E→J and J→S legs near-zero DSM (gravity assists working) ✅
- [x] GTOP Cassini1 benchmark — GTOP-equivalent: 5.47 km/s vs published 4.93 km/s (10.9% gap). Includes Saturn orbit insertion. Trajectory shape correct. ✅

**Success criteria:** Reproduced trajectories match known mission data within 5% delta-v. ✅ Voyager 2 validated.

### Phase 2: Core Engine + API
Build the computation engine and expose it via REST API.

- [x] NHATS API integration — 681 targets at <6 km/s, cached locally
- [x] JPL Small-Body Database integration — orbital elements for any asteroid
- [x] FastAPI REST server (port 8790) with endpoints:
  - `GET /api/planets/:epoch` — all planet positions/velocities ✅
  - `GET /api/planets/:body/orbit` — orbital path points ✅
  - `GET /api/transfer` — Lambert transfer computation + propagated trajectory ✅
  - `GET /api/porkchop` — porkchop plot grid data ✅
  - `GET /api/targets` — NHATS targets with filters ✅
  - `GET /api/targets/:designation` — asteroid orbital elements ✅
- [x] `POST /api/optimize` — MGA-1DSM trajectory optimization ✅
- [x] `GET /api/reference-missions` — 8 historic missions (Voyager 2, Cassini, New Horizons, Galileo, Mariner 10, Juno, Pioneer 10, MESSENGER) ✅
- [x] LRU result caching (transfer: 200, porkchop: 20) ✅
- [x] Earth-to-NEA transfers + porkchop — Keplerian propagation from SBDB orbital elements. 2000 SG344 optimal: 3.28 km/s ✅
- [x] Low-thrust trajectory optimization (Sims-Flanagan method) — Earth-Mars: 3.25 km/s thrust-dv, 105 kg propellant ✅
- [x] Automated gravity assist sequence discovery — three-tier pipeline (enumerate→Lambert prescreen→optimize top N). Earth→Saturn: E→M→J→S (12.0 km/s). Earth→Jupiter: E→V→E→J (VEGA, 14.2 km/s). 3.5x faster than brute-force. ✅
- [ ] Background job system for long-running optimizations

**Success criteria:** API can generate a porkchop plot for any NHATS target in <10s, and optimize a gravity-assist trajectory in <60s.

### Phase 3: Web Frontend
Interactive 3D mission designer in the browser.

- [x] Scaffold React + Vite + R3F + Zustand + Tailwind project (port 5180, proxy to API)
- [x] 3D solar system scene (Sun, 8 planets, orbits, correct positions from SPICE)
- [x] Sidebar with transfer config, stat cards, NEA target list
- [x] Zustand store for all app state
- [x] API client (TypeScript) for all endpoints
- [x] NEA target browser — 200-target table with selection, detail panel in sidebar
- [x] Porkchop plot viewer — canvas heatmap, click-to-select auto-computes transfer
- [x] Transfer trajectory visualization — animated spacecraft along Kepler-propagated arc
- [x] Gravity assist visualization — flyby markers with body-colored rings at encounter points
- [x] Mission event timeline — HUD panel showing encounter dates, Δv gains, progress
- [x] Reference mission viewer — 8 missions with animated playback + planet orbital motion
- [x] Time controls — play/pause + scrubber showing actual dates, adaptive speed
- [x] Camera controls — 4 presets (perspective, top-down, inner, outer) + planet focus buttons
- [x] Guide tab — full educational content with key concepts, how-it-works, dashboard reference
- [x] Terminus-style UI — textured planets, starfield, corner brackets, JetBrains Mono, HUD overlays
- [x] Phase-angle launch window computation — auto-suggests optimal dates per body pair

**Success criteria:** A user can select a NEA, see its orbit, generate a porkchop plot, pick a transfer, and watch the animated trajectory — all in the browser.

### Phase 4: Polish + Deploy
- [x] Loading states, error handling, empty states
- [ ] Deploy backend (Fly.io or Railway — needs Python + spiceypy)
- [ ] Deploy frontend (Vercel)
- [ ] Pre-compute porkchop plots for top 50 most accessible NEAs
- [ ] Performance optimization (WebGL instancing, LOD for orbits)
- [ ] Responsive design for smaller screens
- [ ] Portfolio site integration (embedded 3D preview)

---

## Future Improvements

> **Note:** Re-evaluate whether these make sense in the same app or should be separate projects/tools. Some (like GTOP benchmarking) are pure computation with no UI needed; others (like multi-NEA tours) could be a natural extension of the mission designer.

### Multi-NEA Tour Optimizer
Given NHATS's 6,822 targets, optimize multi-asteroid tours (visit N asteroids with minimum delta-v). This is a Traveling Salesman Problem in 4D (position + time) — transfer costs change with launch windows. GTOC5 (7,075 asteroids) proved this is tractable with good algorithms.

- Likely a separate "tour planner" mode in the same app
- Combinatorial search over asteroid sequences + continuous optimization of dates
- Could use beam search + ant colony (GTOC5 winning approach) or genetic algorithms

### Beat GTOP Benchmarks
The Cassini2, Messenger-full, and Rosetta problems still have room for improvement. A novel metaheuristic or hybrid approach that finds lower-delta-v solutions would be a publishable result.

- Could be a separate CLI tool / research notebook — no UI needed
- Use pygmo island model with custom algorithm variants
- If we beat any benchmark, write it up for publication

### Low-Thrust NEA Mission Catalog
Most NHATS data assumes impulsive (chemical) propulsion. Computing optimal low-thrust (ion/solar sail) trajectories to top NHATS targets would produce a novel dataset.

- Sims-Flanagan method via pykep for preliminary design
- Could add a "propulsion type" toggle to the mission designer (chemical vs. ion vs. solar sail)
- Computationally heavier — may need background job queue

### Gravity Assist Sequence Discovery
Given a target NEA, automatically discover the best gravity assist sequence (which planets, in what order). Currently done by human intuition + brute force enumeration.

- Natural extension of the mission designer — "auto-optimize flyby sequence" button
- Enumerate candidate sequences (constrained by synodic periods, v-infinity matching)
- Run MGA-1DSM optimization on each viable sequence
- Present top N sequences ranked by total delta-v

---

## Key Technical Notes

### Lambert's Problem
The fundamental building block. Given two positions and a time-of-flight, find the transfer orbit. Izzo's algorithm (used by pykep) converges in 3-5 iterations. A porkchop plot is just a grid of Lambert solutions. Performance: ~1-10 microseconds per solve in C++ (pykep), ~100-500 microseconds in pure Python.

### Patched Conics Approximation
Sufficient for preliminary mission design (which is our use case). Treats each flyby as instantaneous — the spacecraft's speed doesn't change relative to the flyby body, but the direction rotates, producing a "free" delta-v in the heliocentric frame. Delta-v error vs. full N-body is typically 50-200 m/s (small compared to 3-10 km/s total budgets).

### Coordinate Systems
- **J2000 equatorial** for state vectors (SPICE default)
- **ECLIPJ2000** for orbital elements and visualization
- **TDB** (Barycentric Dynamical Time) for all epoch calculations — what SPICE calls "ET"

### SPICE Kernel Set (Minimum)
1. `naif0012.tls` — leapseconds
2. `de440s.bsp` — planet ephemerides (32 MB, covers 1849-2150)
3. `pck00011.tpc` — planetary constants (radii, GM)
4. Mission-specific SPKs for validation (Voyager, Cassini, etc.)

---

*Last updated: 2026-03-15*
