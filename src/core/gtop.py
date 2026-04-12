"""ESA GTOP benchmark problem implementations.

Implements the Cassini1 benchmark for comparison against published optimal solutions.

The GTOP Cassini1 is a pure MGA (Multiple Gravity Assist) problem with 6 decision
variables: t0 (departure epoch) and T1-T5 (leg times of flight). No deep-space
maneuvers — only powered flybys at each swing-by body.

The objective includes:
  - Launch v-infinity (departure delta-v)
  - Powered flyby delta-v at each swing-by (periapsis impulse)
  - Saturn orbit insertion delta-v (into orbit with rp=108,950 km, e=0.98)

Reference: https://www.esa.int/gsp/ACT/projects/gtop/cassini1/
Published best: 4.9307 km/s
x* = [-789.625, 158.302, 449.385, 54.7, 1024.36, 4552.76]
"""

import numpy as np
from scipy.optimize import differential_evolution
from typing import Dict, List, Tuple
from .lambert import solve_lambert, solve_lambert_multirev
from .ephemeris import get_body_state, utc_to_et, et_to_utc
from .constants import MU_SUN, MU_SATURN, BODIES
from .jpl_lp import jpl_lp_state, get_gtop_body_params, GTOP_MU_SUN


# --- Powered flyby physics ---

def powered_flyby_dv(v_inf_in: np.ndarray, v_inf_out: np.ndarray,
                     mu_body: float, rp_min: float) -> Tuple[float, float]:
    """Compute delta-v for a powered gravity assist using exact physics.

    Given incoming and outgoing v-infinity vectors, find the periapsis
    radius that achieves the required bending angle, then compute the
    periapsis impulse Δv = |v_p_out - v_p_in|.

    For an unpowered flyby (equal v-inf magnitudes), Δv = 0.
    For a powered flyby, Δv is the cost of changing |v_inf| at periapsis.

    Args:
        v_inf_in: Incoming v-infinity vector (km/s)
        v_inf_out: Outgoing v-infinity vector (km/s)
        mu_body: Body gravitational parameter (km³/s²)
        rp_min: Minimum periapsis radius (km)

    Returns:
        (dv, rp): delta-v cost (km/s) and periapsis radius used (km)
    """
    v_in = np.linalg.norm(v_inf_in)
    v_out = np.linalg.norm(v_inf_out)

    if v_in < 1e-10 or v_out < 1e-10:
        return abs(v_out - v_in), rp_min

    # Required bending angle
    cos_delta = np.dot(v_inf_in, v_inf_out) / (v_in * v_out)
    cos_delta = np.clip(cos_delta, -1.0, 1.0)
    delta_req = np.arccos(cos_delta)

    if delta_req < 1e-12:
        # No bending needed — just speed change at infinite rp
        return abs(v_out - v_in), np.inf

    def total_bending(rp):
        """Sum of half-deflection angles from incoming and outgoing hyperbolas."""
        e_in = 1.0 + rp * v_in ** 2 / mu_body
        e_out = 1.0 + rp * v_out ** 2 / mu_body
        # Guard against numerical issues (e must be > 1 for hyperbola)
        sin_in = min(1.0 / e_in, 1.0)
        sin_out = min(1.0 / e_out, 1.0)
        return np.arcsin(sin_in) + np.arcsin(sin_out)

    # Maximum bending at rp_min
    max_bending = total_bending(rp_min)

    if delta_req > max_bending:
        # Infeasible even at minimum periapsis — use rp_min and add penalty
        rp = rp_min
        v_p_in = np.sqrt(v_in ** 2 + 2 * mu_body / rp)
        v_p_out = np.sqrt(v_out ** 2 + 2 * mu_body / rp)
        dv = abs(v_p_out - v_p_in)
        # Add smooth penalty proportional to the bending deficit
        excess = delta_req - max_bending
        penalty = 0.5 * (v_in + v_out) * excess
        return dv + penalty, rp

    # Find rp that achieves delta_req via bisection
    # total_bending(rp) is monotonically decreasing in rp
    rp_lo = rp_min
    rp_hi = 1e6 * rp_min  # large enough that bending → 0
    # Ensure rp_hi actually gives less bending
    while total_bending(rp_hi) > delta_req:
        rp_hi *= 10

    for _ in range(60):
        rp_mid = (rp_lo + rp_hi) / 2.0
        if total_bending(rp_mid) > delta_req:
            rp_lo = rp_mid
        else:
            rp_hi = rp_mid
        if rp_hi - rp_lo < 1.0:  # 1 km precision
            break

    rp = (rp_lo + rp_hi) / 2.0

    # Periapsis velocities on the two hyperbolas
    v_p_in = np.sqrt(v_in ** 2 + 2 * mu_body / rp)
    v_p_out = np.sqrt(v_out ** 2 + 2 * mu_body / rp)

    return abs(v_p_out - v_p_in), rp


def saturn_orbit_insertion_dv(v_inf: float, mu_saturn: float = None) -> float:
    """Compute delta-v for Saturn orbit insertion.

    Target orbit: rp = 108,950 km, e = 0.98
    This matches the GTOP Cassini1 problem definition.
    """
    if mu_saturn is None:
        mu_saturn = MU_SATURN
    rp_target = 108950.0  # km
    e_target = 0.98

    v_per_hyp = np.sqrt(v_inf ** 2 + 2 * mu_saturn / rp_target)
    a_target = rp_target / (1 - e_target)
    v_per_orb = np.sqrt(mu_saturn * (2 / rp_target - 1 / a_target))

    return abs(v_per_hyp - v_per_orb)


# --- GTOP Cassini1: Pure MGA, 6 decision variables ---

# EVVEJS sequence
CASSINI1_SEQUENCE = ['earth', 'venus', 'venus', 'earth', 'jupiter', 'saturn']

# GTOP bounds (MJD2000 for t0, days for TOFs)
CASSINI1_BOUNDS_MJD = [
    (-1000.0, 0.0),     # t0 (MJD2000)
    (30.0, 400.0),       # T1: E→V
    (100.0, 470.0),      # T2: V→V
    (30.0, 400.0),       # T3: V→E
    (400.0, 2000.0),     # T4: E→J
    (1000.0, 6000.0),    # T5: J→S
]

# MJD2000 epoch = 2000-01-01 12:00 TDB = J2000 + 0.5 days
MJD2000_TO_JD = 2451544.5


_MJD2000_EPOCH_ET = None

def mjd2000_to_et(mjd2000: float) -> float:
    """Convert MJD2000 to SPICE ephemeris time (ET seconds past J2000).

    Uses SPICE for the base epoch conversion (handles UTC-TDB offset exactly),
    then applies a linear offset for the MJD2000 value.
    """
    global _MJD2000_EPOCH_ET
    if _MJD2000_EPOCH_ET is None:
        _MJD2000_EPOCH_ET = utc_to_et('2000-01-01T00:00:00')
    return _MJD2000_EPOCH_ET + mjd2000 * 86400.0


def _evaluate_leg_combo(states, leg_solutions, sequence):
    """Evaluate total dv for a specific combination of Lambert solutions per leg.

    leg_solutions: list of 5 (v1, v2) tuples, one per leg.
    Returns total_dv or np.inf if infeasible.
    """
    v_dep = [sol[0] for sol in leg_solutions]
    v_arr = [sol[1] for sol in leg_solutions]

    # Departure v-infinity
    v_inf_launch = np.linalg.norm(v_dep[0] - states[0][3:])
    total_dv = v_inf_launch

    # Powered flyby at each swing-by
    for i in range(1, 5):
        v_body = states[i][3:]
        v_inf_in = v_arr[i - 1] - v_body
        v_inf_out = v_dep[i] - v_body
        body_name = CASSINI1_SEQUENCE[i]
        mu_body = BODIES[body_name]['mu']
        rp_min = BODIES[body_name].get('rp_min', BODIES[body_name]['radius'] * 1.05)
        dv_flyby, _ = powered_flyby_dv(v_inf_in, v_inf_out, mu_body, rp_min)
        total_dv += dv_flyby

    # Saturn orbit insertion
    v_inf_saturn = np.linalg.norm(v_arr[4] - states[5][3:])
    total_dv += saturn_orbit_insertion_dv(v_inf_saturn)

    return total_dv


def cassini1_evaluate(x: np.ndarray) -> float:
    """Evaluate the GTOP Cassini1 objective function with multi-rev Lambert.

    Tries all Lambert solution branches (0-rev + multi-rev) for each leg
    and picks the combination that minimizes total delta-v.

    Decision variables:
        x[0]: t0 in MJD2000
        x[1:6]: T1-T5 leg times of flight in days

    Returns:
        Total delta-v (km/s) = departure_v_inf + Σ(flyby_dv) + saturn_insertion_dv
    """
    PENALTY = 1e6

    t0_mjd = x[0]
    tofs_days = x[1:6]

    t0_et = mjd2000_to_et(t0_mjd)
    tofs_sec = tofs_days * 86400.0

    epochs = np.zeros(6)
    epochs[0] = t0_et
    for i in range(5):
        epochs[i + 1] = epochs[i] + tofs_sec[i]

    sequence = CASSINI1_SEQUENCE
    states = []
    try:
        for i, body in enumerate(sequence):
            states.append(get_body_state(body, epochs[i]))
    except Exception:
        return PENALTY

    # Solve Lambert for each leg — use multi-rev only for V→V resonance leg
    all_leg_solutions = []
    for leg in range(5):
        r1 = states[leg][:3]
        r2 = states[leg + 1][:3]
        tof = tofs_sec[leg]

        # Only use multi-rev for V→V leg (index 1) and E→V (index 0) where
        # resonance orbits exist. Other legs: 0-rev is optimal.
        use_multirev = leg <= 1 and tof > 150 * 86400
        if use_multirev:
            solutions = solve_lambert_multirev(r1, r2, tof, MU_SUN, max_revs=1)
        else:
            solutions = []

        if not solutions:
            try:
                v1, v2 = solve_lambert(r1, r2, tof, MU_SUN)
                solutions = [(v1, v2)]
            except (ValueError, RuntimeError):
                return PENALTY
        all_leg_solutions.append(solutions)

    # For legs with only 1 solution, no branching needed
    # For legs with multiple solutions, try all combos
    # Optimization: evaluate combos greedily — for each leg, pick the branch
    # that minimizes local flyby cost (greedy is nearly optimal and avoids
    # exponential blowup)
    best_dv = PENALTY
    n_solutions = [len(s) for s in all_leg_solutions]

    if max(n_solutions) == 1:
        # Fast path: no multi-rev branches, single combination
        combo = [sols[0] for sols in all_leg_solutions]
        best_dv = _evaluate_leg_combo(states, combo, sequence)
    else:
        # Try all combinations (product is small: typically ≤ 3^5 = 243)
        from itertools import product
        for indices in product(*(range(n) for n in n_solutions)):
            combo = [all_leg_solutions[leg][idx] for leg, idx in enumerate(indices)]
            dv = _evaluate_leg_combo(states, combo, sequence)
            if dv < best_dv:
                best_dv = dv

    return best_dv


def cassini1_evaluate_detailed(x: np.ndarray) -> Dict:
    """Evaluate with full breakdown for reporting."""
    t0_mjd = x[0]
    tofs_days = x[1:6]

    t0_et = mjd2000_to_et(t0_mjd)
    tofs_sec = tofs_days * 86400.0

    epochs = np.zeros(6)
    epochs[0] = t0_et
    for i in range(5):
        epochs[i + 1] = epochs[i] + tofs_sec[i]

    sequence = CASSINI1_SEQUENCE
    states = [get_body_state(body, epochs[i]) for i, body in enumerate(sequence)]

    v_dep, v_arr = [], []
    for leg in range(5):
        v1, v2 = solve_lambert(states[leg][:3], states[leg + 1][:3], tofs_sec[leg], MU_SUN)
        v_dep.append(v1)
        v_arr.append(v2)

    # Departure
    v_inf_launch = np.linalg.norm(v_dep[0] - states[0][3:])

    # Flybys
    flyby_details = []
    total_flyby_dv = 0.0
    for i in range(1, 5):
        v_body = states[i][3:]
        v_inf_in = v_arr[i - 1] - v_body
        v_inf_out = v_dep[i] - v_body
        body_name = sequence[i]
        mu_body = BODIES[body_name]['mu']
        rp_min = BODIES[body_name].get('rp_min', BODIES[body_name]['radius'] * 1.05)
        dv, rp = powered_flyby_dv(v_inf_in, v_inf_out, mu_body, rp_min)
        total_flyby_dv += dv
        flyby_details.append({
            'body': body_name,
            'v_inf_in': float(np.linalg.norm(v_inf_in)),
            'v_inf_out': float(np.linalg.norm(v_inf_out)),
            'dv': float(dv),
            'rp_km': float(rp),
            'rp_radii': float(rp / BODIES[body_name]['radius']),
            'epoch_utc': et_to_utc(epochs[i]),
        })

    # Saturn insertion
    v_inf_saturn = np.linalg.norm(v_arr[4] - states[5][3:])
    dv_soi = saturn_orbit_insertion_dv(v_inf_saturn)

    total_dv = v_inf_launch + total_flyby_dv + dv_soi

    return {
        'total_dv': float(total_dv),
        'departure_v_inf': float(v_inf_launch),
        'flyby_dv_total': float(total_flyby_dv),
        'saturn_insertion_dv': float(dv_soi),
        'saturn_v_inf': float(v_inf_saturn),
        'flybys': flyby_details,
        'departure_utc': et_to_utc(epochs[0]),
        'arrival_utc': et_to_utc(epochs[5]),
        'total_tof_days': float(sum(tofs_days)),
        'x': x.tolist(),
    }


def cassini1(max_iter: int = 2000, pop_size: int = 80, seed: int = 42,
             n_restarts: int = 20, verbose: bool = True) -> Dict:
    """Run the GTOP Cassini1 benchmark with proper MGA formulation.

    Uses 6 decision variables (t0 + T1-T5), proper powered flyby physics,
    and aggressive multi-restart differential evolution.
    """
    bounds = CASSINI1_BOUNDS_MJD

    best_result = None
    best_dv = np.inf

    strategies = ['best1bin', 'rand1bin', 'currenttobest1bin',
                  'best2bin', 'rand2bin', 'randtobest1bin']

    for i in range(n_restarts):
        restart_seed = seed + i * 137

        strategy = strategies[i % len(strategies)]

        # Alternate between standard and aggressive mutation
        if i % 3 == 0:
            mutation = (0.5, 1.5)
        elif i % 3 == 1:
            mutation = (0.3, 1.0)
        else:
            mutation = (0.7, 1.9)

        result = differential_evolution(
            cassini1_evaluate,
            bounds=bounds,
            maxiter=max_iter,
            popsize=pop_size,
            tol=1e-6,
            seed=restart_seed,
            disp=False,
            polish=True,
            strategy=strategy,
            mutation=mutation,
            recombination=0.9,
            init='latinhypercube',
        )

        if result.fun < best_dv:
            best_dv = result.fun
            best_result = result
            if verbose:
                print(f"  Restart {i + 1}/{n_restarts}: {result.fun:.4f} km/s "
                      f"(strategy={strategy}, nfev={result.nfev})")

    # Get detailed breakdown
    details = cassini1_evaluate_detailed(best_result.x)

    published_best = 4.9307
    details['benchmark'] = {
        'name': 'GTOP Cassini1',
        'published_best_dv': published_best,
        'our_dv': details['total_dv'],
        'gap_percent': (details['total_dv'] / published_best - 1) * 100,
        'ratio': details['total_dv'] / published_best,
        'n_restarts': n_restarts,
        'total_evaluations': sum(1 for _ in range(n_restarts)),  # approximate
    }
    details['optimizer'] = {
        'success': best_result.success,
        'message': best_result.message,
        'n_evaluations': best_result.nfev,
    }

    return details


def cassini1_verify_published() -> Dict:
    """Evaluate our objective at the published best solution to validate our physics.

    Published x* = [-789.625, 158.302, 449.385, 54.7, 1024.36, 4552.76]
    Published f* = 4.9307 km/s

    If our evaluation matches, the physics is correct and the gap is purely optimization.
    If it doesn't match, we have a formulation error to fix.
    """
    x_published = np.array([-789.625, 158.302, 449.385, 54.7, 1024.36, 4552.76])
    details = cassini1_evaluate_detailed(x_published)

    published_best = 4.9307
    details['verification'] = {
        'published_x': x_published.tolist(),
        'published_f': published_best,
        'our_f': details['total_dv'],
        'difference': details['total_dv'] - published_best,
        'match': abs(details['total_dv'] - published_best) < 0.1,
    }

    return details


def cassini1_quick(seed: int = 42) -> Dict:
    """Quick version — fewer restarts and iterations."""
    return cassini1(max_iter=500, pop_size=40, seed=seed, n_restarts=5, verbose=False)


# --- Phase 2: Advanced optimizers ---

def _bounds_lo_hi():
    """Return (lower, upper) arrays from CASSINI1_BOUNDS_MJD."""
    lo = np.array([b[0] for b in CASSINI1_BOUNDS_MJD])
    hi = np.array([b[1] for b in CASSINI1_BOUNDS_MJD])
    return lo, hi


def run_cmaes(n_restarts: int = 8, sigma_frac: float = 0.3,
              max_fevals: int = 80000, seed: int = 42,
              verbose: bool = True) -> Tuple[np.ndarray, float]:
    """Run CMA-ES optimizer on the Cassini1 problem.

    CMA-ES adapts the search covariance matrix, making it effective when
    decision variables are correlated (e.g., t0 and T1 for Venus timing).
    """
    import cma

    lo, hi = _bounds_lo_hi()
    bounds_cma = [lo.tolist(), hi.tolist()]
    rng = np.random.RandomState(seed)

    best_x, best_f = None, np.inf

    for i in range(n_restarts):
        # Random starting point within bounds
        x0 = lo + rng.rand(len(lo)) * (hi - lo)
        sigma0 = sigma_frac * np.min(hi - lo)

        opts = {
            'bounds': bounds_cma,
            'maxfevals': max_fevals,
            'tolfun': 1e-8,
            'tolx': 1e-8,
            'verbose': -9,  # suppress output
            'seed': seed + i * 137,
        }

        try:
            es = cma.CMAEvolutionStrategy(x0.tolist(), sigma0, opts)
            es.optimize(cassini1_evaluate)

            if es.result.fbest < best_f:
                best_f = es.result.fbest
                best_x = np.array(es.result.xbest)
                if verbose:
                    print(f"  CMA-ES R{i + 1}/{n_restarts}: {best_f:.4f} km/s "
                          f"(fevals={es.result.evaluations}) ***BEST***", flush=True)
            elif verbose:
                print(f"  CMA-ES R{i + 1}/{n_restarts}: {es.result.fbest:.4f} km/s", flush=True)
        except Exception as e:
            if verbose:
                print(f"  CMA-ES R{i + 1}/{n_restarts}: failed ({e})", flush=True)

    return best_x, best_f


def run_mbh(n_starts: int = 30, local_maxiter: int = 500,
            n_perturb: int = 15, perturb_scale: float = 0.05,
            seed: int = 42, verbose: bool = True) -> Tuple[np.ndarray, float]:
    """Monotonic Basin Hopping optimizer for Cassini1.

    MBH was developed by ESA's ACT group specifically for interplanetary
    trajectory optimization. It randomly samples starting points, runs a
    local optimizer (Nelder-Mead), and keeps the best. From each new best,
    it applies small perturbations to explore the basin neighborhood.
    """
    from scipy.optimize import minimize

    lo, hi = _bounds_lo_hi()
    scale = hi - lo
    rng = np.random.RandomState(seed)

    best_x, best_f = None, np.inf
    n_evaluated = 0

    for i in range(n_starts):
        # Random starting point
        x0 = lo + rng.rand(len(lo)) * scale

        result = minimize(cassini1_evaluate, x0, method='Nelder-Mead',
                          options={'maxiter': local_maxiter, 'xatol': 1e-6, 'fatol': 1e-8})
        n_evaluated += result.nfev

        improved = False
        if result.fun < best_f:
            best_f = result.fun
            best_x = result.x.copy()
            improved = True

        # Perturbation phase: explore around current best
        if best_x is not None:
            for _ in range(n_perturb):
                dx = rng.randn(len(lo)) * perturb_scale * scale
                x_pert = np.clip(best_x + dx, lo, hi)

                result2 = minimize(cassini1_evaluate, x_pert, method='Nelder-Mead',
                                   options={'maxiter': local_maxiter, 'xatol': 1e-6, 'fatol': 1e-8})
                n_evaluated += result2.nfev

                if result2.fun < best_f:
                    best_f = result2.fun
                    best_x = result2.x.copy()
                    improved = True

        if verbose and improved:
            print(f"  MBH start {i + 1}/{n_starts}: {best_f:.4f} km/s "
                  f"(total fevals={n_evaluated}) ***BEST***", flush=True)

    if verbose:
        print(f"  MBH total evaluations: {n_evaluated}", flush=True)

    return best_x, best_f


def cassini1_ensemble(de_restarts: int = 6, cma_restarts: int = 6,
                      mbh_starts: int = 20, seed: int = 42,
                      verbose: bool = True) -> Dict:
    """Run DE + CMA-ES + MBH ensemble and return the best result.

    Each algorithm explores the search space differently:
    - DE: population-based, good at global exploration
    - CMA-ES: covariance-adaptive, good at correlated landscapes
    - MBH: local-search-based, good at finding basin minima
    """
    import gc

    lo, hi = _bounds_lo_hi()
    best_x, best_f = None, np.inf

    # --- DE ---
    if verbose:
        print("=== Differential Evolution ===", flush=True)
    strategies = ['best1bin', 'rand1bin', 'currenttobest1bin',
                  'best2bin', 'rand2bin', 'randtobest1bin']
    mutations = [(0.5, 1.5), (0.3, 1.0), (0.7, 1.9), (0.4, 1.2), (0.6, 1.8), (0.5, 1.5)]

    for i in range(de_restarts):
        gc.collect()
        result = differential_evolution(
            cassini1_evaluate, bounds=CASSINI1_BOUNDS_MJD,
            maxiter=800, popsize=40, tol=1e-6,
            seed=seed + i * 137, disp=False, polish=True,
            strategy=strategies[i % len(strategies)],
            mutation=mutations[i % len(mutations)],
            recombination=0.9, init='latinhypercube',
        )
        tag = ''
        if result.fun < best_f:
            best_f = result.fun
            best_x = result.x.copy()
            tag = ' ***BEST***'
        if verbose:
            print(f"  DE R{i + 1}/{de_restarts}: {result.fun:.4f} km/s{tag}", flush=True)

    # --- CMA-ES ---
    if verbose:
        print("=== CMA-ES ===", flush=True)
    gc.collect()
    cma_x, cma_f = run_cmaes(n_restarts=cma_restarts, seed=seed + 1000, verbose=verbose)
    if cma_x is not None and cma_f < best_f:
        best_f = cma_f
        best_x = cma_x

    # --- MBH ---
    if verbose:
        print("=== Monotonic Basin Hopping ===", flush=True)
    gc.collect()
    mbh_x, mbh_f = run_mbh(n_starts=mbh_starts, seed=seed + 2000, verbose=verbose)
    if mbh_x is not None and mbh_f < best_f:
        best_f = mbh_f
        best_x = mbh_x

    # --- Local polish from best point with multiple methods ---
    if verbose:
        print("=== Local polish ===", flush=True)
    from scipy.optimize import minimize
    for method in ['Nelder-Mead', 'Powell']:
        try:
            result = minimize(cassini1_evaluate, best_x, method=method,
                              options={'maxiter': 2000, 'xatol': 1e-10, 'fatol': 1e-10})
            if result.fun < best_f:
                best_f = result.fun
                best_x = result.x.copy()
                if verbose:
                    print(f"  {method}: {result.fun:.4f} km/s ***IMPROVED***", flush=True)
        except Exception:
            pass

    # Get detailed breakdown
    details = cassini1_evaluate_detailed(best_x)

    published_best = 4.9307
    details['benchmark'] = {
        'name': 'GTOP Cassini1',
        'published_best_dv': published_best,
        'our_dv': details['total_dv'],
        'gap_percent': (details['total_dv'] / published_best - 1) * 100,
        'ratio': details['total_dv'] / published_best,
    }

    return details


# --- GTOP Analytical Ephemeris versions ---

def cassini1_gtop_evaluate(x: np.ndarray) -> float:
    """Evaluate Cassini1 using the GTOP analytical ephemeris (jpl_lp).

    This uses the exact same planet positions as the published benchmark,
    enabling apples-to-apples comparison against the 4.9307 km/s result.
    """
    PENALTY = 1e6

    t0_mjd = x[0]
    tofs_days = x[1:6]

    # Encounter epochs in MJD2000
    epochs_mjd = np.zeros(6)
    epochs_mjd[0] = t0_mjd
    for i in range(5):
        epochs_mjd[i + 1] = epochs_mjd[i] + tofs_days[i]

    # Get body states from analytical ephemeris
    sequence = CASSINI1_SEQUENCE
    states = []
    try:
        for i, body in enumerate(sequence):
            states.append(jpl_lp_state(body, epochs_mjd[i]))
    except Exception:
        return PENALTY

    # Solve Lambert for each leg (using GTOP mu_sun)
    v_dep, v_arr = [], []
    for leg in range(5):
        r1 = states[leg][:3]
        r2 = states[leg + 1][:3]
        tof = tofs_days[leg] * 86400.0
        try:
            v1, v2 = solve_lambert(r1, r2, tof, GTOP_MU_SUN)
        except (ValueError, RuntimeError):
            return PENALTY
        v_dep.append(v1)
        v_arr.append(v2)

    # Departure v-infinity
    v_inf_launch = np.linalg.norm(v_dep[0] - states[0][3:])
    total_dv = v_inf_launch

    # Powered flybys at rp_min (max Oberth) + bending feasibility check
    for i in range(1, 5):
        v_body = states[i][3:]
        v_inf_in = v_arr[i - 1] - v_body
        v_inf_out = v_dep[i] - v_body
        vi_mag = np.linalg.norm(v_inf_in)
        vo_mag = np.linalg.norm(v_inf_out)
        body_name = sequence[i]
        params = get_gtop_body_params(body_name)
        rp = params['rp_min']
        mu_b = params['mu']

        # Periapsis impulse (Oberth-enhanced speed change)
        vp_in = np.sqrt(vi_mag ** 2 + 2 * mu_b / rp)
        vp_out = np.sqrt(vo_mag ** 2 + 2 * mu_b / rp)
        dv_flyby = abs(vp_out - vp_in)

        # Bending feasibility check
        if vi_mag > 1e-10 and vo_mag > 1e-10:
            cos_delta = np.dot(v_inf_in, v_inf_out) / (vi_mag * vo_mag)
            cos_delta = np.clip(cos_delta, -1.0, 1.0)
            delta_req = np.arccos(cos_delta)
            e_in = 1.0 + rp * vi_mag ** 2 / mu_b
            e_out = 1.0 + rp * vo_mag ** 2 / mu_b
            delta_max = np.arcsin(min(1.0 / e_in, 1.0)) + np.arcsin(min(1.0 / e_out, 1.0))
            if delta_req > delta_max:
                excess = delta_req - delta_max
                dv_flyby += 0.5 * (vi_mag + vo_mag) * excess

        total_dv += dv_flyby

    # Saturn orbit insertion (using GTOP Saturn mu)
    saturn_params = get_gtop_body_params('saturn')
    v_inf_saturn = np.linalg.norm(v_arr[4] - states[5][3:])
    dv_soi = saturn_orbit_insertion_dv(v_inf_saturn, mu_saturn=saturn_params['mu'])
    total_dv += dv_soi

    return total_dv


def cassini1_gtop_verify() -> Dict:
    """Verify our GTOP ephemeris by evaluating the published best solution."""
    x_pub = np.array([-789.625, 158.302, 449.385, 54.7, 1024.36, 4552.76])
    f = cassini1_gtop_evaluate(x_pub)
    return {
        'published_f': 4.9307,
        'our_f': float(f),
        'difference': float(f - 4.9307),
        'x': x_pub.tolist(),
    }


def cassini1_gtop_run(n_restarts: int = 15, max_iter: int = 800,
                      pop_size: int = 40, seed: int = 42,
                      verbose: bool = True) -> Dict:
    """Run Cassini1 with GTOP analytical ephemeris — apples-to-apples benchmark."""
    import gc
    from scipy.optimize import minimize

    bounds = CASSINI1_BOUNDS_MJD
    strategies = ['best1bin', 'rand1bin', 'currenttobest1bin',
                  'best2bin', 'rand2bin', 'randtobest1bin']
    mutations = [(0.5, 1.5), (0.3, 1.0), (0.7, 1.9), (0.4, 1.2), (0.6, 1.8), (0.5, 1.5)]

    best_x, best_f = None, np.inf

    for i in range(n_restarts):
        gc.collect()
        r = differential_evolution(
            cassini1_gtop_evaluate, bounds=bounds,
            maxiter=max_iter, popsize=pop_size, tol=1e-6,
            seed=seed + i * 137, disp=False, polish=True,
            strategy=strategies[i % len(strategies)],
            mutation=mutations[i % len(mutations)],
            recombination=0.9, init='latinhypercube',
        )
        tag = ''
        if r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()
            tag = ' ***BEST***'
        if verbose:
            print(f'  DE R{i + 1:2d}: {r.fun:.4f}{tag}', flush=True)

    # Local polish
    for method in ['Nelder-Mead', 'Powell']:
        try:
            r = minimize(cassini1_gtop_evaluate, best_x, method=method,
                         options={'maxiter': 5000, 'xatol': 1e-12, 'fatol': 1e-12})
            if r.fun < best_f:
                best_f = r.fun
                best_x = r.x.copy()
                if verbose:
                    print(f'  {method}: {r.fun:.4f} ***IMPROVED***', flush=True)
        except Exception:
            pass

    published_best = 4.9307
    return {
        'total_dv': float(best_f),
        'published_best': published_best,
        'gap_percent': float((best_f / published_best - 1) * 100),
        'x': best_x.tolist(),
    }
