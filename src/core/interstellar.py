"""Interstellar Precursor mission — maximize heliocentric escape velocity.

Unlike other missions, the objective is to MAXIMIZE asymptotic velocity
(interstellar cruise speed) using gravity assists from the outer planets.

The asymptotic escape velocity from the Sun is:
    v_inf_escape² = 2 × (specific_energy) = v² - 2μ/r

For a given position r, a higher |v| gives a higher v_inf_escape.
We measure the spacecraft's specific energy after the last flyby and
convert to asymptotic escape velocity.
"""

import numpy as np
import gc
from typing import Dict, Tuple, List
from scipy.optimize import differential_evolution

from .jpl_lp import jpl_lp_state, get_gtop_body_params, GTOP_MU_SUN, GTOP_AU_KM
from .lambert import solve_lambert
from .propagate import propagate_kepler
from .gtop_cassini2 import _unpowered_flyby
from .island_model import run_archipelago


def _asymptotic_velocity(r: np.ndarray, v: np.ndarray, mu: float = GTOP_MU_SUN) -> float:
    """Compute asymptotic escape velocity from heliocentric state.

    v_inf² = v² - 2μ/r  (for hyperbolic trajectory)
    Returns 0 if trajectory is elliptic (not escaping).
    """
    v_sq = float(np.dot(v, v))
    r_mag = float(np.linalg.norm(r))
    energy = 0.5 * v_sq - mu / r_mag
    if energy <= 0:
        return 0.0
    return float(np.sqrt(2.0 * energy))


def make_interstellar_evaluator(sequence: List[str]):
    """Build an evaluator that MINIMIZES negative asymptotic escape velocity.

    Decision variables (same layout as Cassini2 MGA-1DSM):
        t0, Vinf, u, v, T1..Tn, eta1..etan, rp1..rp(n-1), beta1..beta(n-1)
    """
    n_bodies = len(sequence)
    n_legs = n_bodies - 1
    PENALTY = 1e6

    flyby_params = [get_gtop_body_params(sequence[i]) for i in range(1, n_bodies)]

    def evaluate(x):
        t0 = x[0]
        vinf_mag = x[1]
        u, v = x[2], x[3]
        tofs = x[4:4 + n_legs]
        etas = x[4 + n_legs:4 + 2 * n_legs]
        rps = x[4 + 2 * n_legs:4 + 3 * n_legs - 1] if n_legs > 1 else np.array([])
        betas = x[4 + 3 * n_legs - 1:4 + 4 * n_legs - 2] if n_legs > 1 else np.array([])

        epochs = np.zeros(n_bodies)
        epochs[0] = t0
        for i in range(n_legs):
            epochs[i + 1] = epochs[i] + tofs[i]

        try:
            states = [jpl_lp_state(body, epochs[i]) for i, body in enumerate(sequence)]
        except Exception:
            return PENALTY

        theta = 2.0 * np.pi * u
        phi = np.arccos(2.0 * v - 1.0) - np.pi / 2.0
        v_sc = states[0][3:].copy()
        v_sc[0] += vinf_mag * np.cos(phi) * np.cos(theta)
        v_sc[1] += vinf_mag * np.cos(phi) * np.sin(theta)
        v_sc[2] += vinf_mag * np.sin(phi)

        # Track DSM costs — we want to include launch v_inf as cost
        # because in reality the launcher limits C3, but allow free flybys
        total_dv = vinf_mag

        r_final = None
        v_final = None

        for leg in range(n_legs):
            tof_sec = tofs[leg] * 86400.0
            eta = etas[leg]
            dt_coast = eta * tof_sec
            dt_lambert = (1.0 - eta) * tof_sec
            if dt_lambert < 1.0:
                return PENALTY

            try:
                r_dsm, v_bal = propagate_kepler(states[leg][:3], v_sc, dt_coast, GTOP_MU_SUN)
                v_ls, v_le = solve_lambert(r_dsm, states[leg + 1][:3], dt_lambert, GTOP_MU_SUN)
            except Exception:
                return PENALTY
            if not (np.all(np.isfinite(r_dsm)) and np.all(np.isfinite(v_ls))):
                return PENALTY

            dsm = float(np.linalg.norm(v_ls - v_bal))
            if not np.isfinite(dsm):
                return PENALTY
            total_dv += dsm

            if leg < n_legs - 1:
                body = sequence[leg + 1]
                params = flyby_params[leg]
                rp_km = rps[leg] * params['radius']
                v_sc = _unpowered_flyby(v_le, states[leg + 1][3:], params['mu'],
                                         rp_km, betas[leg])
                if not np.all(np.isfinite(v_sc)):
                    return PENALTY
            else:
                # Final body: perform unpowered flyby to maximize escape
                body = sequence[leg + 1]
                params = flyby_params[leg]
                rp_km = rps[-1] * params['radius'] if n_legs > 1 else params['radius'] * 1.1
                beta_last = betas[-1] if n_legs > 1 else 0.0
                v_final = _unpowered_flyby(v_le, states[leg + 1][3:], params['mu'],
                                            rp_km, beta_last)
                r_final = states[leg + 1][:3].copy()

        # Hard budget: real interstellar precursors are limited to ~15 km/s
        # total impulsive delta-v (launch + DSMs). Beyond that, penalize.
        DV_BUDGET = 15.0
        if total_dv > DV_BUDGET:
            return PENALTY + (total_dv - DV_BUDGET) * 100.0

        # Compute asymptotic escape velocity
        v_inf_escape = _asymptotic_velocity(r_final, v_final)

        # Objective: maximize v_inf_escape (negative for minimizer)
        # Small preference for lower dv to break ties
        return -(v_inf_escape - 0.05 * total_dv)

    return evaluate


def _build_interstellar_bounds(sequence, dep_window, tof_ranges,
                               vinf_range=(3.0, 12.0)):
    n_legs = len(sequence) - 1

    SAFE_FACTORS = {
        'venus': (1.1, 6), 'earth': (1.1, 6), 'mars': (1.1, 6),
        'jupiter': (1.7, 50), 'saturn': (1.1, 30),
    }

    bounds = [dep_window, vinf_range, (0.0, 1.0), (0.0, 1.0)]
    for i in range(n_legs):
        bounds.append(tof_ranges[i])
    for _ in range(n_legs):
        bounds.append((0.01, 0.9))
    # Include flyby rp for ALL bodies after launch (including final body)
    for i in range(1, len(sequence)):
        lo, hi = SAFE_FACTORS.get(sequence[i], (1.1, 30))
        bounds.append((lo, hi))
    for _ in range(1, len(sequence)):
        bounds.append((-np.pi, np.pi))
    return bounds


def optimize_interstellar(sequence: List[str],
                          dep_window: Tuple[float, float],
                          tof_ranges: List[Tuple[float, float]],
                          vinf_range=(3.0, 12.0),
                          n_arch: int = 8, n_gen: int = 1500,
                          verbose: bool = True) -> Dict:
    """Optimize an interstellar precursor trajectory."""
    evaluate = make_interstellar_evaluator(sequence)
    bounds = _build_interstellar_bounds(sequence, dep_window, tof_ranges, vinf_range)
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    best_x, best_f = None, np.inf
    for run in range(n_arch):
        gc.collect()
        x, f = run_archipelago(evaluate, bounds,
            n_islands=8, pop_per_island=25, n_generations=n_gen, migrate_every=40,
            seed=42 + run * 1777, verbose=False)
        if f < best_f:
            best_f = f
            best_x = x.copy()
        if verbose:
            print(f'  Arch {run + 1}/{n_arch}: score={-f:.3f}{" ***BEST***" if f == best_f else ""}', flush=True)

    # Narrow refinement
    narrow = [(max(lo[i], best_x[i] - 0.1 * (hi[i] - lo[i])),
               min(hi[i], best_x[i] + 0.1 * (hi[i] - lo[i]))) for i in range(len(bounds))]
    for i in range(3):
        gc.collect()
        r = differential_evolution(evaluate, bounds=narrow, maxiter=500, popsize=30,
            tol=1e-8, seed=9999 + i, disp=False, polish=True,
            strategy='best1bin', mutation=(0.3, 1.0))
        if np.isfinite(r.fun) and r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()

    # Compute breakdown
    return _interstellar_breakdown(best_x, sequence)


def _interstellar_breakdown(x, sequence):
    """Full breakdown of an interstellar trajectory."""
    from datetime import datetime, timedelta

    n_bodies = len(sequence)
    n_legs = n_bodies - 1
    t0 = x[0]
    vinf_mag = x[1]
    u, v = x[2], x[3]
    tofs = x[4:4 + n_legs]
    etas = x[4 + n_legs:4 + 2 * n_legs]
    rps = x[4 + 2 * n_legs:4 + 3 * n_legs - 1] if n_legs > 1 else np.array([])
    betas = x[4 + 3 * n_legs - 1:4 + 4 * n_legs - 2] if n_legs > 1 else np.array([])

    epochs = np.zeros(n_bodies)
    epochs[0] = t0
    for i in range(n_legs):
        epochs[i + 1] = epochs[i] + tofs[i]

    states = [jpl_lp_state(body, epochs[i]) for i, body in enumerate(sequence)]

    theta = 2.0 * np.pi * u
    phi = np.arccos(2.0 * v - 1.0) - np.pi / 2.0
    v_sc = states[0][3:].copy()
    v_sc[0] += vinf_mag * np.cos(phi) * np.cos(theta)
    v_sc[1] += vinf_mag * np.cos(phi) * np.sin(theta)
    v_sc[2] += vinf_mag * np.sin(phi)

    total_dv = vinf_mag
    dsm_dvs = []
    flyby_dates = []

    for leg in range(n_legs):
        tof_sec = tofs[leg] * 86400.0
        eta = etas[leg]
        r_dsm, v_bal = propagate_kepler(states[leg][:3], v_sc, eta * tof_sec, GTOP_MU_SUN)
        v_ls, v_le = solve_lambert(r_dsm, states[leg + 1][:3],
                                    (1 - eta) * tof_sec, GTOP_MU_SUN)
        dsm = float(np.linalg.norm(v_ls - v_bal))
        dsm_dvs.append(dsm)
        total_dv += dsm

        params = get_gtop_body_params(sequence[leg + 1])
        if leg < n_legs - 1:
            rp_km = rps[leg] * params['radius']
            v_sc = _unpowered_flyby(v_le, states[leg + 1][3:], params['mu'], rp_km, betas[leg])
        else:
            # Final flyby
            rp_km = rps[-1] * params['radius'] if n_legs > 1 else params['radius'] * 1.1
            beta_last = betas[-1] if n_legs > 1 else 0.0
            v_sc = _unpowered_flyby(v_le, states[leg + 1][3:], params['mu'], rp_km, beta_last)

    v_inf_escape = _asymptotic_velocity(states[-1][:3], v_sc)

    # AU/year conversion
    au_per_year = v_inf_escape * 86400 * 365.25 / GTOP_AU_KM

    base = datetime(2000, 1, 1)
    return {
        'sequence': sequence,
        'v_inf_escape_km_s': float(v_inf_escape),
        'v_inf_escape_au_per_year': float(au_per_year),
        'launch_vinf_km_s': float(vinf_mag),
        'launch_c3': float(vinf_mag ** 2),
        'total_dsm_km_s': float(sum(dsm_dvs)),
        'total_dv_km_s': float(total_dv),
        'total_tof_years': float(sum(tofs) / 365.25),
        'departure_date': (base + __import__('datetime').timedelta(days=float(t0))).strftime('%Y-%m-%d'),
        'last_flyby_date': (base + __import__('datetime').timedelta(days=float(epochs[-1]))).strftime('%Y-%m-%d'),
        'years_to_200au': float(200.0 / au_per_year) if au_per_year > 0 else float('inf'),
        'x': x.tolist(),
    }


def propagate_interstellar_mission(x, sequence: List[str]) -> Dict:
    """Propagate an interstellar precursor for visualization.

    Includes a post-flyby "escape tail" showing the spacecraft leaving the solar system.
    """
    from datetime import datetime, timedelta

    n_bodies = len(sequence)
    n_legs = n_bodies - 1
    t0 = x[0]
    vinf_mag = x[1]
    u, v = x[2], x[3]
    tofs = x[4:4 + n_legs]
    etas = x[4 + n_legs:4 + 2 * n_legs]
    rps = x[4 + 2 * n_legs:4 + 3 * n_legs - 1] if n_legs > 1 else np.array([])
    betas = x[4 + 3 * n_legs - 1:4 + 4 * n_legs - 2] if n_legs > 1 else np.array([])

    epochs = np.zeros(n_bodies)
    epochs[0] = t0
    for i in range(n_legs):
        epochs[i + 1] = epochs[i] + tofs[i]

    BODY_NAMES = {'venus': 'Venus', 'earth': 'Earth', 'mars': 'Mars',
                  'jupiter': 'Jupiter', 'saturn': 'Saturn', 'mercury': 'Mercury'}

    states = [jpl_lp_state(body, epochs[i]) for i, body in enumerate(sequence)]

    theta = 2.0 * np.pi * u
    phi = np.arccos(2.0 * v - 1.0) - np.pi / 2.0
    v_sc = states[0][3:].copy()
    v_sc[0] += vinf_mag * np.cos(phi) * np.cos(theta)
    v_sc[1] += vinf_mag * np.cos(phi) * np.sin(theta)
    v_sc[2] += vinf_mag * np.sin(phi)

    positions = []
    events = []
    base = datetime(2000, 1, 1)

    def fmt(d): return (base + timedelta(days=float(d))).strftime('%Y-%m-%d')

    events.append({
        'body': BODY_NAMES.get(sequence[0], sequence[0].title()),
        'date': fmt(epochs[0]), 'type': 'launch',
        'distance_km': 0, 'dv_gained_km_s': 0,
        'heliocentric_position_km': states[0][:3].tolist(),
    })

    for leg in range(n_legs):
        tof_sec = tofs[leg] * 86400.0
        eta = etas[leg]
        dt_coast = eta * tof_sec
        dt_lambert = (1.0 - eta) * tof_sec

        # Ballistic coast
        n_coast = max(30, int(dt_coast / 86400 / 2))
        dt_step = dt_coast / max(n_coast - 1, 1)
        r_cur, v_cur = states[leg][:3].copy(), v_sc.copy()
        for p in range(n_coast):
            positions.append(r_cur.tolist())
            if p < n_coast - 1:
                r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_step, GTOP_MU_SUN)

        r_dsm, v_bal = propagate_kepler(states[leg][:3], v_sc, dt_coast, GTOP_MU_SUN)
        v_ls, v_le = solve_lambert(r_dsm, states[leg + 1][:3], dt_lambert, GTOP_MU_SUN)

        # Lambert arc
        n_lamb = max(30, int(dt_lambert / 86400 / 2))
        dt_step_l = dt_lambert / max(n_lamb - 1, 1)
        r_cur, v_cur = r_dsm.copy(), v_ls.copy()
        for p in range(n_lamb):
            positions.append(r_cur.tolist())
            if p < n_lamb - 1:
                r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_step_l, GTOP_MU_SUN)

        params = get_gtop_body_params(sequence[leg + 1])
        if leg < n_legs - 1:
            rp_km = rps[leg] * params['radius']
            v_sc = _unpowered_flyby(v_le, states[leg + 1][3:], params['mu'], rp_km, betas[leg])
            events.append({
                'body': BODY_NAMES.get(sequence[leg + 1], sequence[leg + 1].title()),
                'date': fmt(epochs[leg + 1]), 'type': 'flyby',
                'distance_km': int(rp_km),
                'dv_gained_km_s': 0,
                'heliocentric_position_km': states[leg + 1][:3].tolist(),
            })
        else:
            # Final flyby
            rp_km = rps[-1] * params['radius'] if n_legs > 1 else params['radius'] * 1.1
            beta_last = betas[-1] if n_legs > 1 else 0.0
            v_sc = _unpowered_flyby(v_le, states[leg + 1][3:], params['mu'], rp_km, beta_last)
            events.append({
                'body': BODY_NAMES.get(sequence[leg + 1], sequence[leg + 1].title()),
                'date': fmt(epochs[leg + 1]), 'type': 'flyby',
                'distance_km': int(rp_km),
                'dv_gained_km_s': 0,
                'heliocentric_position_km': states[leg + 1][:3].tolist(),
            })

    # Escape tail: propagate 25 years past last flyby
    v_inf_escape = _asymptotic_velocity(states[-1][:3], v_sc)
    tail_years = 25.0
    tail_sec = tail_years * 365.25 * 86400
    n_tail = 100
    dt_tail = tail_sec / max(n_tail - 1, 1)
    r_cur, v_cur = states[-1][:3].copy(), v_sc.copy()
    for p in range(n_tail):
        positions.append(r_cur.tolist())
        if p < n_tail - 1:
            r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_tail, GTOP_MU_SUN)

    # Escape "arrival" event — 25 years post-flyby
    escape_mjd = epochs[-1] + tail_years * 365.25
    events.append({
        'body': f'Escape ({v_inf_escape:.1f} km/s asymptotic)',
        'date': fmt(escape_mjd), 'type': 'arrival',
        'distance_km': int(np.linalg.norm(r_cur) / 1e6),
        'dv_gained_km_s': round(float(v_inf_escape), 2),
        'heliocentric_position_km': r_cur.tolist(),
    })

    bd = _interstellar_breakdown(x, sequence)
    return {
        'events': events,
        'trajectory_positions': positions,
        'sequence': [BODY_NAMES.get(s, s.title()) for s in sequence] + ['Escape'],
        'stats': {
            'v_inf_escape_km_s': bd['v_inf_escape_km_s'],
            'v_inf_escape_au_per_year': bd['v_inf_escape_au_per_year'],
            'years_to_200_au': bd['years_to_200au'],
            'launch_c3': bd['launch_c3'],
            'total_dv_km_s': bd['total_dv_km_s'],
            'total_tof_years': bd['total_tof_years'] + tail_years,
        },
    }


def compare_interstellar_sequences(dep_window: Tuple[float, float],
                                    verbose: bool = True) -> List[Dict]:
    """Compare interstellar precursor sequences."""
    candidates = [
        ('E→J', ['earth', 'jupiter'], [(400, 2000)]),
        ('E→J→S', ['earth', 'jupiter', 'saturn'], [(400, 2000), (800, 3000)]),
        ('E→V→E→J', ['earth', 'venus', 'earth', 'jupiter'],
         [(100, 400), (200, 600), (400, 2000)]),
        ('E→E→J', ['earth', 'earth', 'jupiter'], [(200, 600), (400, 2000)]),
        ('E→J→S→...', ['earth', 'jupiter', 'saturn'], [(400, 2000), (800, 4000)]),
    ]

    results = []
    for name, seq, tofs in candidates:
        if verbose:
            print(f'\n--- {name} ---', flush=True)
        try:
            r = optimize_interstellar(seq, dep_window, tofs, n_arch=5, n_gen=1500, verbose=verbose)
            r['name'] = name
            results.append(r)
            if verbose:
                print(f'  => v_inf={r["v_inf_escape_km_s"]:.2f} km/s '
                      f'({r["v_inf_escape_au_per_year"]:.2f} AU/yr), '
                      f'200AU in {r["years_to_200au"]:.0f}yr, '
                      f'C3={r["launch_c3"]:.1f}', flush=True)
        except Exception as e:
            if verbose:
                print(f'  Failed: {e}', flush=True)

    results.sort(key=lambda r: -r['v_inf_escape_km_s'])  # highest first
    return results
