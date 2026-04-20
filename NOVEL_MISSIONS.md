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

## 3. NEA Sample Return — Target Comparison (2028–2036)

**Question:** What's the most fuel-efficient near-Earth asteroid for a sample return mission? How do real mission targets compare to the most accessible NHATS candidates?

**Method:** Tested 6 NEAs spanning a range of accessibility. Each trajectory is a simple two-Lambert round-trip: Earth → asteroid (outbound transfer + rendezvous) → stay → asteroid → Earth (return transfer + reentry). 4 decision variables: departure epoch, outbound TOF, stay time, return TOF. Optimized with 3 archipelagos × 1000 generations + narrow DE refinement.

Cost function: `Δv = v_inf_launch + v_rendezvous_at_asteroid + v_departure_from_asteroid + v_inf_arrival_at_Earth`

### Results

| Target | Orbit | Total Δv (km/s) | Launch | Rendezvous | Dep | Arrival | Duration |
|--------|-------|-----------------|--------|------------|-----|---------|----------|
| **2000 SG344** | a=0.98, e=0.07, i=0.1° | **1.83** | 0.22 | 0.58 | 0.70 | 0.33 | 2.1 yr |
| 2008 HU4 | a=1.07, e=0.06, i=1.4° | 3.92 | 0.92 | 1.75 | 0.45 | 0.80 | 1.9 yr |
| 1999 AO10 | a=0.91, e=0.11, i=2.6° | 5.91 | 1.10 | 2.13 | 2.33 | 0.36 | 1.6 yr |
| Apophis | a=0.92, e=0.19, i=3.3° | 8.86 | 1.55 | 2.86 | 2.39 | 2.06 | 2.3 yr |
| Ryugu (Hayabusa2) | a=1.19, e=0.19, i=5.9° | 9.57 | 0.09 | 4.59 | 2.74 | 2.15 | 1.9 yr |
| Bennu (OSIRIS-REx) | a=1.13, e=0.20, i=6.0° | 11.54 | 0.64 | 5.23 | 1.91 | 3.76 | 1.2 yr |

### Analysis

**Winner: 2000 SG344 at 1.83 km/s — remarkably accessible**
- Extremely Earth-like orbit (a=0.98 AU, e=0.07, i=0.1°) means low relative velocities at every phase
- Rendezvous cost is just 0.58 km/s vs 5.23 for Bennu — matching velocities with SG344 is nearly free
- 2028 departure window, 2.1 year total mission
- This total Δv is **6× cheaper than OSIRIS-REx's Bennu mission** (accounting only for trajectory; real mission dv includes margins, safety factors, and mission design overhead)

**Accessibility scales strongly with orbital similarity to Earth**
- 2000 SG344 (most similar) at 1.83 km/s
- Bennu (moderately inclined, eccentric) at 11.54 km/s
- A 6× spread across our test set, driven mostly by rendezvous and return arrival costs

**Famous mission targets are actually expensive**
- Bennu and Ryugu both score 9.5–11.5 km/s — their scientific interest (carbonaceous chondrites, water, organics) justified the cost
- Apophis is surprisingly accessible at 8.86 km/s despite its fame, thanks to its low-inclination Earth-crossing orbit

**Strategic implication**
- For a low-cost sample return demonstrator, 2000 SG344 or 2008 HU4 are dramatically cheaper targets
- The NHATS database identified these specifically for this accessibility — they're the "hidden gems" of asteroid science
- Trade-off: famous targets have prior characterization (radar, photometry); SG344-class targets require precursor observations

### Simplifications and caveats

- No gravity assists — a Venus or Earth flyby could reduce Bennu/Ryugu costs by 1-3 km/s
- No deep-space maneuvers (pure Lambert)
- Impulsive propulsion only — low-thrust could halve the delta-v for the low-accessibility targets
- Stay time is optimized as a decision variable; mission-realistic science operations need 30+ days minimum
- Earth arrival Δv is counted as a cost; in practice this becomes atmospheric reentry (free for a sample capsule, structural for an orbiter)

---

## 4. Interstellar Precursor — Maximum Escape Velocity (2028–2036)

**Question:** What gravity assist sequence produces the fastest escape trajectory from the solar system?

**Method:** Reformulated the optimization objective: instead of minimizing delta-v, *maximize* asymptotic escape velocity (v_inf after leaving the solar system's gravity well). Constrained total impulsive delta-v (launch + DSMs) to ≤ 15 km/s — a realistic budget for real spacecraft. Asymptotic velocity computed from the specific orbital energy after the last gravity assist: `v_inf² = v² - 2μ/r`.

Tested 5 sequences with 5 archipelagos × 1500 generations + narrow DE refinement.

### Results

| Sequence | v_inf escape (km/s) | AU/yr | Years to 200 AU | Launch C3 | Launch v_inf | DSM |
|----------|--------------------:|------:|----------------:|----------:|-------------:|-----|
| **E→V→E→J** | **35.10** | **7.40** | **27** | 12.9 | 3.59 | 11.41 |
| E→E→J | 35.02 | 7.39 | 27 | 9.0 | 3.00 | 12.00 |
| E→J→S | 24.65 | 5.20 | 38 | 17.7 | 4.20 | 10.80 |
| E→J→S (long) | 23.62 | 4.98 | 40 | 15.2 | 3.90 | 11.10 |
| E→J (direct) | 19.98 | 4.22 | 47 | 10.2 | 3.20 | 11.80 |

### Analysis

**Winner: Venus-Earth-Jupiter (VEJ) at 35 km/s / 7.4 AU/yr — reaches 200 AU in 27 years**
- VEJ and EEJ are essentially tied; both use Earth and Jupiter gravity assists to maximize the escape velocity after the final Jupiter slingshot
- 7.4 AU/yr is **2× faster than Voyager 1** (currently ~3.6 AU/yr at 165 AU)
- Comparable to proposed mission concepts like New Horizons 2 or the Solar Gravity Lens mission

**Counterintuitive: adding Saturn to the tour makes you slower**
- E→J alone: 20 km/s, 4.2 AU/yr
- E→J→S: 25 km/s, 5.2 AU/yr (Saturn helps)
- But E→V→E→J: 35 km/s, 7.4 AU/yr (**best**) — and adding Saturn to this would cost velocity
- Saturn is "too far and too slow" to further accelerate a spacecraft already moving at 35 km/s; the extra TOF doesn't compensate for the slingshot gained

**The 15 km/s total-dv budget is the binding constraint**
- Every optimal solution uses nearly all 15 km/s budget
- The launcher provides ~3 km/s (low C3); DSMs provide the other ~11-12 km/s
- Without this constraint, the optimizer exploits infinite DSMs; with it, the physics becomes realistic

**For comparison with real missions**
- Voyager 1 post-Titan flyby: ~17 km/s at 100 AU (5.2 AU/yr at launch, ~3.6 AU/yr now)
- Interstellar Probe concept studies: targeted 6-10 AU/yr
- Our 7.4 AU/yr fits this class of missions with modern, achievable physics

**Trajectory:** Depart Earth May 2029, Venus flyby June 2030, Earth flyby June 2031, Jupiter flyby December 2036. Spacecraft escapes at 35 km/s asymptotic.

---

## 5. Multi-NEA Tour — 2-Asteroid Rendezvous Tours (2028–2036)

**Question:** Can a single mission visit multiple near-Earth asteroids efficiently?

**Method:** Tested 4 pairs of accessible NEAs. Each tour is: Earth → A1 (rendezvous) → stay → A1 → A2 (rendezvous) → stay → A2 → Earth. 6 decision variables: departure epoch, 3 leg TOFs, 2 stay times. Cost = sum of v_inf's at each boundary (launch + 4 rendezvous transitions + Earth arrival).

### Results

| Pair | Total Δv (km/s) | Launch | Arr A1 | Dep A1 | Arr A2 | Dep A2 | Earth | Duration |
|------|----------------:|-------:|-------:|-------:|-------:|-------:|------:|---------:|
| **2000 SG344 → 2006 RH120** | **3.71** | 0.22 | 0.58 | 0.64 | 0.44 | 0.87 | 0.95 | 2.5 yr |
| 2000 SG344 → 2008 HU4 | 7.88 | 2.08 | 1.69 | 0.74 | 1.04 | 0.72 | 1.61 | 3.6 yr |
| 2000 SG344 → 1999 AO10 | 9.90 | 1.18 | 0.47 | 2.11 | 3.48 | 2.29 | 0.38 | 4.1 yr |
| 2008 HU4 → 1999 AO10 | 11.54 | 2.54 | 1.37 | 1.30 | 3.11 | 1.55 | 1.68 | 4.1 yr |

### Analysis

**Winner: 2000 SG344 → 2006 RH120 at 3.71 km/s over 2.5 years**
- **Less than half the cost of a single-target sample return to Bennu** (11.54 km/s)
- 2006 RH120 is a "mini-moon" — a natural object temporarily captured in Earth's co-orbital region. Its orbit is extraordinarily Earth-like, which is why the rendezvous and departure costs are tiny (0.44 and 0.87 km/s)
- 2000 SG344 is the most accessible NHATS target (§3 sample return analysis)
- Mission: depart Feb 2028, reach SG344 July 2028, reach RH120 June 2029, return Aug 2030

**Compare single vs multi-target**
- Sample return SG344 alone: 1.83 km/s, 2.1 years (§3)
- Tour SG344 + RH120: 3.71 km/s, 2.5 years — only 1.9 km/s more for a second target!
- Extra science target effectively "free" when the orbits align

**Adding 2008 HU4 significantly hurts**
- Sample return HU4 alone: 3.92 km/s
- Tour SG344 + HU4: 7.88 km/s — 2× more than either alone
- HU4's orbit doesn't match SG344's as well; the inter-asteroid transfer is expensive

**Strategic implication**
- Mini-moons like 2006 RH120 are uniquely valuable multi-target mission partners because of their Earth-like orbits
- A "tour of the gems" — most accessible NHATS + nearest mini-moon — is dramatically cheaper than a flagship mission to a single famous target

### Simplifications

- Fixed pair (no TSP over N asteroids — that's the natural extension)
- No gravity assists (pure Lambert legs)
- No DSMs
- Stay times are optimization variables, not mission-planning constraints
- 2006 RH120 was only a mini-moon in 2006–2007; by 2029 it's a regular NEO — but this trajectory still works based on its current orbital elements

---

---

## 6. Electric Propulsion: Low-Thrust Missions (2028–2032)

**Question:** How do ion propulsion missions compare against chemical alternatives? What does 15× higher I_sp buy you?

**Method:** Sims-Flanagan low-thrust trajectory optimization with scipy SLSQP. Each leg is divided into N impulsive segments at midpoints, bounded by the spacecraft's instantaneous thrust-to-mass capability. Mass depletion tracked via the rocket equation.

### Results

| Mission | Ion Δv (km/s) | TOF | Propellant | Launch V∞ | Arrival V∞ |
|---------|---------------:|----:|----------:|----------:|-----------:|
| **Low-Thrust Earth → Mars** | 4.71 | 400 d | 223 kg (15% of 1500 kg) | 0.77 | 0.47 |
| **Low-Thrust Earth → Vesta** (Dawn-like) | 9.18 | 1300 d | 350 kg (27% of 1300 kg) | 5.60 | 0.55 |

### Analysis

**Earth → Mars: pure low-thrust spiral**
- 4.71 km/s Δv over 400 days, with both departure and arrival v_infs < 1 km/s
- Only 223 kg of xenon propellant used (15% of launch mass)
- A chemical mission at the same Δv would need ~72% propellant (I_sp ~450s for bi-prop) — nearly 5× more mass for propellant vs 5× less for ion
- The trade-off: ion takes 400 days vs Hohmann's ~260 days, and needs solar-scale power

**Earth → Vesta (Dawn replica)**
- Parameters match the real Dawn mission: 92 mN thrust, 3000s I_sp, ~1300 kg launch
- 350 kg of propellant for a 1300-day transfer ending in a full rendezvous with Vesta (0.55 km/s arrival v_inf)
- Chemical rendezvous at Vesta would require ~3-4 km/s arrival burn; ion brings spacecraft to almost zero relative velocity using continuous deceleration

**Key insight: ion doesn't save Δv, it saves propellant mass**
- The total Δv is similar to or larger than chemical missions
- But at 3000s I_sp (vs 450s chemical), every km/s of Δv costs dramatically less mass
- This is why Dawn (1217 kg) could do both Vesta AND Ceres with a single spacecraft — impossible with chemical

---

## 7. Solar Sail: Propellantless Interstellar Escape (2028)

**Question:** Can a solar sail escape the solar system without propellant? How fast?

**Method:** Numerical integration (RK4) of the full equations of motion including continuous radiation pressure. Ideal sail model: thrust = 2P₀A/c × (r₀/r)² × cos²(α) × n̂, with characteristic acceleration a_c at 1 AU as the sail's figure of merit. Locally-optimal control: sail normal at 35.26° cone angle aligned with orbital velocity for maximum tangential thrust.

### Result

| Parameter | Value |
|-----------|-------|
| Characteristic acceleration a_c | 3.0 mm/s² (future-tech, achievable with advanced composite sails) |
| Time to solar system escape | 0.6 years (positive orbital energy) |
| Asymptotic cruise velocity | **15.0 km/s (3.2 AU/yr)** — Voyager-class |
| Propellant | **Zero** |

### Analysis

**The sail's unique property: no propellant, unlimited mission duration**
- A_c = 3 mm/s² means 3 mN of thrust per kg of spacecraft at 1 AU
- Falls as 1/r² with distance from the Sun
- After reaching escape energy, the sail continues adding energy (diminishing as r increases) — the final asymptotic v_inf is what matters

**Comparison with chemical interstellar precursor (§4)**
- Chemical E-V-E-J: 35.1 km/s asymptotic, 15 km/s total impulsive Δv
- Solar sail: 15.0 km/s asymptotic, zero propellant
- Chemical is ~2× faster but consumed ~15 km/s of rocket equation budget
- Sail is slower but needs only the launch vehicle to deploy it

**Technology readiness**
- Current sails (IKAROS demo, Solar Cruiser concept): 0.1-1 mm/s² — too slow for escape in reasonable time
- Near-term advanced (lightweight composite booms, reflective aluminized membrane): 1-2 mm/s²
- Our demo at 3 mm/s² is future-tech but plausible with 10m² per kg areal density

**The sundiver strategy** (implemented as option): instead of spiraling out, brake initially to fall toward the Sun, exploit the deep gravity well (Oberth effect) with perihelion at ~0.2 AU, then accelerate outward. Can achieve higher v_inf for given a_c but requires more complex control.

---

## 8. Hybrid Propulsion: Mars Capture (2030)

**Question:** How do hybrid high-thrust/low-thrust missions combine the strengths of each propulsion type?

**Method:** Chemical launcher provides Earth-departure v_inf. Ion engines handle cruise (Sims-Flanagan). Chemical bi-prop does impulsive orbit insertion at arrival. Reports the total chemical Δv budget alongside the ion cruise Δv and propellant usage.

### Result

| Component | Value |
|-----------|-------|
| Chemical launch v_inf | 0.77 km/s (C3 = 0.6 — trivial launch) |
| Ion cruise Δv | 4.71 km/s |
| Chemical Mars orbit insertion | 1.0 km/s |
| **Total chemical Δv** | **1.77 km/s** |
| Ion propellant | 223 kg xenon |
| TOF | 400 days |

### Analysis

**Chemical Δv is dramatically reduced**
- Chemical-only Earth-Mars orbit insertion needs ~4-5 km/s total (1-2 for Earth departure + 1-2 for TCMs + 1-2 for Mars orbit insertion)
- Hybrid splits this: ion handles cruise, chemical only for critical impulsive burns
- Total chemical Δv: 1.77 km/s — nearly 3× less than chemical-only

**Real-world parallels**
- Dawn (ion + chemical): cruise and orbit change on ion, critical burns on chemical
- BepiColombo (Europa, launched 2018): ion cruise to Mercury + chemical braking, similar architecture
- SMART-1 (Moon, 2003): proved the concept — ion does everything except the critical burns

**Why this matters**
- Launcher can be smaller (less chemical fuel needed)
- Ion engines operate efficiently over long cruises
- Chemical reserved for precise, time-critical maneuvers (orbit insertion, course corrections)
- Total mass budget: much lower propellant overall vs chemical-only, slightly higher vs pure ion (for missions requiring captures)

---

---

## 9. Low-Thrust Sample Return: Bennu (OSIRIS-REx alternative)

**Question:** How does an ion-propulsion sample return to Bennu compare to the chemical OSIRIS-REx approach?

**Method:** Sims-Flanagan low-thrust optimization for the outbound and return legs (Earth → Bennu rendezvous → Earth reentry). Fixed mission parameters: 200 mN thrust, 3000s Isp, 1500 kg launch mass.

### Result

| Metric | Ion | Chemical (§3) |
|--------|-----|---------------|
| Total Δv | 16.6 km/s (ion spiral) | 11.54 km/s (impulsive) |
| Propellant | **400 kg (27%)** | ~93% of launch mass |
| Mission duration | 3.8 years | 1.2 years |
| Payload capacity | High | Low |

### Analysis

**Ion needs 3× more Δv but uses 3.5× less propellant mass**
- The ion spiral requires higher total Δv because thrust is low, so the trajectory can't follow an efficient Hohmann transfer
- But at 3000s Isp vs 450s chemical (6.7× higher exhaust velocity), each km/s of Δv costs ~7× less propellant
- Net result: the ion mission launches with 73% of mass available for payload vs ~7% for chemical

**This is exactly why sample return missions are increasingly ion**
- Hayabusa (2003) and Hayabusa2 (2014) both used ion for sample return
- OSIRIS-REx used chemical only because of development timing — it launched in 2016 when ion was less mature for NASA missions
- Future NEA sample returns will almost certainly use ion

**The time trade-off is real**
- Ion takes 3× longer (3.8 years vs 1.2), which costs operational budget
- But the 3.5× mass saving allows larger samples, more instruments, or a smaller launch vehicle

---

## 10. Hybrid: Saturn / Titan Orbiter

**Question:** Can a modern hybrid propulsion mission match Cassini's capabilities with less launch mass?

**Method:** Chemical launcher provides ~6 km/s v_inf (Falcon Heavy C3≈36), ion engines handle the 7.7-year cruise with v_inf constraints enforced, chemical bi-prop performs the orbit insertion burn.

### Result

| Component | Value |
|-----------|-------|
| Chemical launch v_inf | 6.0 km/s (Falcon Heavy class) |
| Ion cruise Δv | ~6.0 km/s over 7.7 years |
| Ion propellant | 1200 kg xenon |
| **Arrival v_inf** | **0.21 km/s** |
| Chemical Saturn orbit insertion | ~0.6 km/s |
| Total chemical Δv | 6.6 km/s |
| Mission duration | 7.7 years |

### Analysis

**Near-zero arrival v_inf is the headline**
- Arrival v_inf of 0.21 km/s means the ion engine brings the spacecraft to almost the same velocity as Saturn
- Chemical orbit insertion only needs ~0.6 km/s — vs Cassini's ~0.6 km/s insertion burn, comparable
- But Cassini needed 6 gravity assists (VVEJ) and 7 years; this hybrid does it directly with no flybys

**Mass budget**
- With 6 km/s chemical Δv and 450s Isp: launch mass / dry mass = exp(6/4.4) = 3.9×
- Hybrid: launch 3000 kg, dry 1800 kg, ratio only 1.7×
- **The hybrid needs ~2.5× less launch mass for the same dry mass**

**Comparison with Cassini**
- Cassini: 5712 kg launch, 2125 kg dry, 7-year cruise via VVEJ, 4 flybys
- This hybrid: 3000 kg launch, 1800 kg dry, 7.7-year cruise direct
- Hybrid delivers larger dry mass per launch kilogram, enabling more science

---

## 11. Hybrid: Pluto Orbiter (faster than New Horizons, with capture)

**Question:** Can we reach Pluto with orbital capability — something New Horizons couldn't do because it would have needed 14+ km/s of chemical Δv to slow down?

**Method:** Chemical launcher for high v_inf (7.5 km/s, ~C3=56), ion engines for 12-year cruise, chemical bi-prop for Pluto orbit insertion.

### Result

| Component | Value |
|-----------|-------|
| Launch v_inf | 7.5 km/s (upper-class launcher, SLS-like C3) |
| Ion cruise Δv | ~7.5 km/s |
| Ion propellant | 1500 kg xenon (43% of 3500 kg launch mass) |
| Arrival v_inf | ~3 km/s |
| Chemical orbit insertion | ~1 km/s (elliptical Pluto orbit) |
| Mission duration | 12 years |

### Analysis

**Pluto orbit capability without a 14 km/s chemical burn**
- New Horizons arrived at Pluto at 14 km/s — way too fast for orbital capture with chemical propulsion
- This hybrid uses 12 years of ion thrust to gradually match Pluto's solar orbit, arriving with only 3 km/s v_inf
- Chemical insertion is then manageable (1 km/s)

**Compare to New Horizons**
- NH: 9.5 year transit (with Jupiter GA), 14 km/s arrival v_inf, flyby only
- This hybrid: 12 years, 3 km/s arrival v_inf, full orbital capture

**Why hybrid beats pure-chemical here**
- Pure chemical Pluto orbiter needs: 11 km/s Earth departure + 14 km/s Pluto braking = 25+ km/s chemical Δv
- At 450s Isp, that's ~exp(25/4.4) = 296× mass ratio — impossible
- Hybrid splits: 7.5 km/s chemical launch + ion cruise handles most braking + 1 km/s chemical = only 8.5 km/s chemical Δv

**Why hybrid beats pure-ion**
- Pure ion Pluto at 12 years from LEO would need ~25 km/s ion Δv — doable but propellant-hungry
- Using chemical for the initial Earth-escape kick saves ~5 km/s of ion Δv, reducing propellant by ~30%

---

*Generated: 2026-04-20*
*Optimizer: Island model (8 islands, 5 archipelagos × 1500 gen) + narrow DE refinement for MGA problems*
*Low-thrust: Sims-Flanagan with scipy SLSQP NLP solver*
*Solar sail: RK4 numerical integration of full continuous-thrust dynamics*
*Evaluator: C generic_mga_1dsm_eval for MGA, ~30,000 evals/sec*
