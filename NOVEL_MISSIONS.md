# Novel Mission Designs

Optimized interplanetary trajectories designed by I.C.A.R.U.S. using the MGA-1DSM framework, C evaluation engine (30K evals/sec), and island model optimizer (DE + PSO with migration).

All trajectories use the JPL low-precision analytical ephemeris (Standish 1992) and impulsive (chemical) propulsion.

---

## 1. Modern Grand Tour — Outer Solar System (2028–2035)

**Question:** What's the best multi-planet outer solar system tour available in near-future launch windows?

**Method:** Tested 5 candidate flyby sequences with MGA-1DSM optimization. Each sequence was optimized with 5 archipelagos × 1500 generations + narrow DE refinement. Departure window: 2028–2035 (MJD2000 10227–12784).

### Results

| Rank | Sequence | Total Δv (km/s) | TOF (years) | Launch C3 (km²/s²) | Departure | Arrival |
|------|----------|-----------------|-------------|---------------------|-----------|---------|
| 1 | E→E→J→S | **8.80** | 13.4 | 2.6 | 2033-07-14 | 2046-11 |
| 2 | E→V→E→J→S | 9.04 | 12.2 | 1.0 | 2034-08-06 | 2046-10 |
| 3 | E→V→E→J (Jupiter only) | 10.18 | 4.6 | 1.0 | 2028-04-02 | 2032-10 |
| 4 | E→J→S (direct) | 11.48 | 13.8 | 20.3 | 2033-10-07 | 2047-07 |
| 5 | E→V→E→J→S→U (with Uranus) | 12.18 | 21.5 | 1.0 | 2034-07-14 | 2056-01 |

### Analysis

**Winner: Earth-Earth-Jupiter-Saturn (EEJS)**
- The Earth resonance flyby builds up energy before the Jupiter leg, reducing total Δv by 0.24 km/s vs the Venus-Earth approach
- Very low C3 (2.6 km²/s²) — launchable by almost any modern rocket
- 13.4 years is long but comparable to Cassini's actual 7-year cruise (which didn't go to Saturn orbit insertion with as low Δv)

**Venus-Earth-Jupiter-Saturn (VEJS) is a close second**
- Only 0.24 km/s more expensive
- C3 of 1.0 km²/s² is essentially the minimum possible — the spacecraft barely escapes Earth
- The Venus flyby provides the energy boost that the EEJS gets from the Earth resonance

**Adding Uranus is expensive**
- +3.4 km/s and +9 years over EEJS
- The Uranus leg requires a long coast from Saturn (Saturn-Uranus distance is ~10 AU)
- A dedicated Uranus mission via Jupiter gravity assist would likely be more efficient than extending a Saturn tour

**Jupiter-only (VEJ) is the fast option**
- 4.6 years and C3=1.0 — ideal for a Europa Clipper-class mission
- 10.18 km/s total Δv is moderate; the real Clipper used VEEGA and cost ~8.5 km/s

**All optimal departures cluster in 2033–2034**
- Suggests a favorable Jupiter-Saturn alignment in that window
- The 2028 departure (Jupiter-only) uses a different alignment, indicating the Venus-Earth-Jupiter geometry is good around 2028

### Decision Variables (EEJS winner)

The winning trajectory has 18 decision variables:
- t0 (departure MJD2000), Vinf, u, v (departure direction)
- T1–T3 (leg times of flight), eta1–eta3 (DSM fractions)
- rp1–rp2 (flyby periapsis radii), beta1–beta2 (flyby plane angles)

---

*Generated: 2026-04-16*
*Optimizer: Island model (8 islands, 5 archipelagos × 1500 gen) + narrow DE refinement*
*Evaluator: C generic_mga_1dsm_eval, ~30,000 evals/sec*
