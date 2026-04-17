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

---

## 2. Fast Jupiter/Europa — Sequence Comparison (2028–2035)

**Question:** What's the most fuel-efficient path to Jupiter for a Europa Clipper-class mission? How do different gravity assist sequences compare?

**Method:** Tested 7 candidate sequences with MGA-1DSM optimization. Departure window 2028–2035. Each sequence optimized with 5 archipelagos × 1500 generations + narrow DE refinement.

### Results

| Rank | Sequence | Total Δv (km/s) | TOF (years) | Launch C3 (km²/s²) | Dep Vinf (km/s) | Departure |
|------|----------|-----------------|-------------|---------------------|-----------------|-----------|
| 1 | E→E→Ma→J | **10.07** | 6.0 | 1.1 | 1.03 | 2034-07-05 |
| 2 | E→V→E→J | 10.18 | 4.6 | 1.0 | 1.01 | 2028-04-02 |
| 3 | E→Ma→E→J | 10.66 | 6.5 | 1.0 | 1.00 | 2033-06-24 |
| 4 | E→V→E→E→J | 10.73 | 5.1 | 1.0 | 1.00 | 2032-12-11 |
| 5 | E→V→V→E→J | 11.22 | 8.6 | 9.4 | 3.06 | 2032-08-03 |
| 6 | E→E→J | 11.81 | 6.2 | 1.9 | 1.38 | 2032-05-14 |
| 7 | E→J (direct) | 14.36 | 2.9 | 75.5 | 8.69 | 2028-12-24 |

### Analysis

**Winner: Earth-Earth-Mars-Jupiter (E→E→Ma→J) at 10.07 km/s**
- Surprising — Mars assists aren't commonly used for Jupiter missions, but the Earth resonance + Mars flyby provides an efficient energy buildup
- Departure July 2034 with C3=1.1 — trivial launch requirement
- 6.0 years is longer than VEJ (4.6yr) but saves 0.11 km/s

**Venus-Earth-Jupiter (VEJ) is the fastest practical option**
- 4.6 years and 10.18 km/s — the classic VEGA-like trajectory
- Departure April 2028, the earliest window in our range
- Best for missions that prioritize fast arrival over fuel efficiency

**Direct transfer is prohibitively expensive**
- 14.36 km/s and C3=75.5 — requires a massive launch vehicle
- Only 2.9 years, but the fuel cost makes it impractical for most missions
- The real Europa Clipper uses VEEGA specifically to avoid this

**Mars assists are competitive with Venus assists**
- E→E→Ma→J (10.07) beats E→V→E→J (10.18) by 0.11 km/s
- E→Ma→E→J (10.66) is also competitive
- Mars flybys are underexplored in the literature — most Europa studies focus on Venus

**Double flybys add TOF without proportional benefit**
- VVEJ (11.22 km/s, 8.6yr) is worse than VEJ (10.18, 4.6yr) — the extra Venus loop costs 4 years for 1 km/s worse
- VEEJ (10.73, 5.1yr) is only 0.55 km/s worse than VEJ and takes 0.5yr longer — marginal benefit for the complexity

### For a Europa Clipper-class mission

If constrained to C3 < 10 km²/s² and TOF < 7 years:
- **Best: E→V→E→J** (10.18 km/s, 4.6yr, C3=1.0) — fastest, proven trajectory topology
- **Runner-up: E→E→Ma→J** (10.07 km/s, 6.0yr, C3=1.1) — lowest Δv but 1.4yr longer

---

*Generated: 2026-04-16*
*Optimizer: Island model (8 islands, 5 archipelagos × 1500 gen) + narrow DE refinement*
*Evaluator: C generic_mga_1dsm_eval, ~30,000 evals/sec*
