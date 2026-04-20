"""NEA Sample Return mission optimization.

Designs round-trip trajectories: Earth → Asteroid → Earth with stay time
at the asteroid for sampling. Two Lambert legs joined by a rendezvous.

Cost function (simple direct mode):
    J = v_inf_launch + v_rendezvous_at_asteroid + v_dep_asteroid + v_inf_arrival_earth

Decision variables (4):
    t0: Earth departure epoch (MJD2000)
    T_out: outbound time of flight (days)
    T_stay: stay time at asteroid (days)
    T_ret: return time of flight (days)
"""

import numpy as np
import gc
from typing import Dict, List, Tuple
from scipy.optimize import differential_evolution, minimize

from .jpl_lp import jpl_lp_state, GTOP_MU_SUN, GTOP_AU_KM
from .lambert import solve_lambert
from .kepler import propagate_state_from_elements
from .island_model import run_archipelago


def _asteroid_state(elements: Dict, mjd2000: float) -> np.ndarray:
    """Compute asteroid state from SBDB Keplerian elements at MJD2000 epoch."""
    # SBDB epoch is in JD; convert our MJD2000 to JD
    target_jd = 2451544.5 + mjd2000
    epoch_jd = elements.get('epoch_jd', 2460200.5)
    return propagate_state_from_elements(
        elements['a'], elements['e'], elements['i'],
        elements['om'], elements['w'], elements['ma'],
        epoch_jd, target_jd,
    )


def make_sample_return_evaluator(asteroid_elements: Dict):
    """Build a round-trip evaluator for a given asteroid."""
    PENALTY = 1e6

    def evaluate(x):
        t0, T_out, T_stay, T_ret = x[0], x[1], x[2], x[3]

        # Encounter epochs
        t_arr_ast = t0 + T_out
        t_dep_ast = t_arr_ast + T_stay
        t_arr_earth = t_dep_ast + T_ret

        try:
            # Body states
            r_e0 = jpl_lp_state('earth', t0)
            r_a1 = _asteroid_state(asteroid_elements, t_arr_ast)
            r_a2 = _asteroid_state(asteroid_elements, t_dep_ast)
            r_e1 = jpl_lp_state('earth', t_arr_earth)

            # Outbound Lambert: Earth → Asteroid
            v1_out, v2_out = solve_lambert(r_e0[:3], r_a1[:3],
                                            T_out * 86400.0, GTOP_MU_SUN)
            # Return Lambert: Asteroid → Earth
            v1_ret, v2_ret = solve_lambert(r_a2[:3], r_e1[:3],
                                            T_ret * 86400.0, GTOP_MU_SUN)
        except Exception:
            return PENALTY

        # Check finite
        if not (np.all(np.isfinite(v1_out)) and np.all(np.isfinite(v2_out)) and
                np.all(np.isfinite(v1_ret)) and np.all(np.isfinite(v2_ret))):
            return PENALTY

        # Costs
        vinf_launch = np.linalg.norm(v1_out - r_e0[3:])       # Earth departure
        vinf_arr_ast = np.linalg.norm(v2_out - r_a1[3:])      # asteroid rendezvous
        vinf_dep_ast = np.linalg.norm(v1_ret - r_a2[3:])      # asteroid departure
        vinf_arr_earth = np.linalg.norm(v2_ret - r_e1[3:])    # Earth arrival

        total = vinf_launch + vinf_arr_ast + vinf_dep_ast + vinf_arr_earth
        return total if np.isfinite(total) else PENALTY

    return evaluate


def sample_return_breakdown(x, asteroid_elements: Dict) -> Dict:
    """Return full cost breakdown for a solution."""
    t0, T_out, T_stay, T_ret = x[0], x[1], x[2], x[3]

    t_arr_ast = t0 + T_out
    t_dep_ast = t_arr_ast + T_stay
    t_arr_earth = t_dep_ast + T_ret

    r_e0 = jpl_lp_state('earth', t0)
    r_a1 = _asteroid_state(asteroid_elements, t_arr_ast)
    r_a2 = _asteroid_state(asteroid_elements, t_dep_ast)
    r_e1 = jpl_lp_state('earth', t_arr_earth)

    v1_out, v2_out = solve_lambert(r_e0[:3], r_a1[:3], T_out * 86400.0, GTOP_MU_SUN)
    v1_ret, v2_ret = solve_lambert(r_a2[:3], r_e1[:3], T_ret * 86400.0, GTOP_MU_SUN)

    from datetime import datetime, timedelta
    base = datetime(2000, 1, 1)

    return {
        'asteroid': asteroid_elements.get('name', 'unknown'),
        'departure_date': (base + timedelta(days=t0)).strftime('%Y-%m-%d'),
        'arrival_asteroid_date': (base + timedelta(days=t_arr_ast)).strftime('%Y-%m-%d'),
        'departure_asteroid_date': (base + timedelta(days=t_dep_ast)).strftime('%Y-%m-%d'),
        'return_date': (base + timedelta(days=t_arr_earth)).strftime('%Y-%m-%d'),
        'outbound_days': float(T_out),
        'stay_days': float(T_stay),
        'return_days': float(T_ret),
        'total_duration_days': float(T_out + T_stay + T_ret),
        'total_duration_years': float((T_out + T_stay + T_ret) / 365.25),
        'v_inf_launch': float(np.linalg.norm(v1_out - r_e0[3:])),
        'v_rendezvous_asteroid': float(np.linalg.norm(v2_out - r_a1[3:])),
        'v_departure_asteroid': float(np.linalg.norm(v1_ret - r_a2[3:])),
        'v_inf_arrival_earth': float(np.linalg.norm(v2_ret - r_e1[3:])),
        'total_dv': float(np.linalg.norm(v1_out - r_e0[3:]) +
                          np.linalg.norm(v2_out - r_a1[3:]) +
                          np.linalg.norm(v1_ret - r_a2[3:]) +
                          np.linalg.norm(v2_ret - r_e1[3:])),
    }


def optimize_sample_return(asteroid_elements: Dict,
                           dep_window: Tuple[float, float] = (10227, 13149),
                           out_tof_range: Tuple[float, float] = (100, 800),
                           stay_range: Tuple[float, float] = (30, 500),
                           ret_tof_range: Tuple[float, float] = (100, 800),
                           n_arch: int = 5, n_gen: int = 1500,
                           verbose: bool = True) -> Dict:
    """Optimize a round-trip sample return mission."""
    evaluate = make_sample_return_evaluator(asteroid_elements)
    bounds = [dep_window, out_tof_range, stay_range, ret_tof_range]
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    best_x, best_f = None, np.inf
    for run in range(n_arch):
        gc.collect()
        x, f = run_archipelago(evaluate, bounds,
            n_islands=8, pop_per_island=20, n_generations=n_gen, migrate_every=40,
            seed=42 + run * 1777, verbose=False)
        if f < best_f:
            best_f = f
            best_x = x.copy()
        if verbose:
            print(f'  Arch {run + 1}/{n_arch}: {f:.4f} km/s{" ***BEST***" if f == best_f else ""}', flush=True)

    # Narrow refinement
    narrow = [(max(lo[i], best_x[i] - 0.1 * (hi[i] - lo[i])),
               min(hi[i], best_x[i] + 0.1 * (hi[i] - lo[i]))) for i in range(4)]
    for i in range(3):
        gc.collect()
        r = differential_evolution(evaluate, bounds=narrow, maxiter=500,
            popsize=30, tol=1e-8, seed=9999 + i, disp=False, polish=True,
            strategy='best1bin', mutation=(0.3, 1.0))
        if np.isfinite(r.fun) and r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()

    breakdown = sample_return_breakdown(best_x, asteroid_elements)
    breakdown['x'] = best_x.tolist()
    return breakdown


def propagate_sample_return_mission(x, asteroid_elements: Dict) -> Dict:
    """Propagate a full sample return trajectory for visualization.

    Returns the same format as gtop_missions / reference missions:
    events, trajectory_positions, sequence, stats.
    """
    from .propagate import propagate_kepler
    from datetime import datetime, timedelta

    t0, T_out, T_stay, T_ret = x[0], x[1], x[2], x[3]
    t_arr_ast = t0 + T_out
    t_dep_ast = t_arr_ast + T_stay
    t_arr_earth = t_dep_ast + T_ret

    r_e0 = jpl_lp_state('earth', t0)
    r_a1 = _asteroid_state(asteroid_elements, t_arr_ast)
    r_a2 = _asteroid_state(asteroid_elements, t_dep_ast)
    r_e1 = jpl_lp_state('earth', t_arr_earth)

    v1_out, v2_out = solve_lambert(r_e0[:3], r_a1[:3], T_out * 86400.0, GTOP_MU_SUN)
    v1_ret, v2_ret = solve_lambert(r_a2[:3], r_e1[:3], T_ret * 86400.0, GTOP_MU_SUN)

    base = datetime(2000, 1, 1)
    positions = []

    # Outbound leg (fine resolution)
    n_out = max(40, int(T_out / 2))
    dt_step = T_out * 86400.0 / max(n_out - 1, 1)
    r_cur, v_cur = r_e0[:3].copy(), v1_out.copy()
    for p in range(n_out):
        positions.append(r_cur.tolist())
        if p < n_out - 1:
            r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_step, GTOP_MU_SUN)

    # Stay at asteroid (follow asteroid position through stay period)
    n_stay = max(10, int(T_stay / 10))
    for p in range(n_stay):
        frac = p / max(n_stay - 1, 1)
        t_current = t_arr_ast + frac * T_stay
        r_ast = _asteroid_state(asteroid_elements, t_current)
        positions.append(r_ast[:3].tolist())

    # Return leg (fine resolution)
    n_ret = max(40, int(T_ret / 2))
    dt_step_r = T_ret * 86400.0 / max(n_ret - 1, 1)
    r_cur, v_cur = r_a2[:3].copy(), v1_ret.copy()
    for p in range(n_ret):
        positions.append(r_cur.tolist())
        if p < n_ret - 1:
            r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_step_r, GTOP_MU_SUN)

    # Event timeline
    def fmt_date(mjd):
        return (base + timedelta(days=mjd)).strftime('%Y-%m-%d')

    # Use designation if name is empty/parenthesized (some NEAs only have "(2000 SG344)")
    raw_name = asteroid_elements.get('name', '')
    parsed = raw_name.split('(')[0].strip()
    ast_name = parsed if parsed else asteroid_elements.get('des', 'Asteroid')

    events = [
        {'body': 'Earth', 'date': fmt_date(t0), 'type': 'launch',
         'distance_km': 0, 'dv_gained_km_s': 0,
         'heliocentric_position_km': r_e0[:3].tolist()},
        {'body': ast_name, 'date': fmt_date(t_arr_ast), 'type': 'flyby',
         'distance_km': 0, 'dv_gained_km_s': round(float(np.linalg.norm(v2_out - r_a1[3:])), 2),
         'heliocentric_position_km': r_a1[:3].tolist()},
        {'body': ast_name, 'date': fmt_date(t_dep_ast), 'type': 'flyby',
         'distance_km': 0, 'dv_gained_km_s': round(float(np.linalg.norm(v1_ret - r_a2[3:])), 2),
         'heliocentric_position_km': r_a2[:3].tolist()},
        {'body': 'Earth', 'date': fmt_date(t_arr_earth), 'type': 'arrival',
         'distance_km': 0, 'dv_gained_km_s': round(float(np.linalg.norm(v2_ret - r_e1[3:])), 2),
         'heliocentric_position_km': r_e1[:3].tolist()},
    ]

    bd = sample_return_breakdown(x, asteroid_elements)
    return {
        'events': events,
        'trajectory_positions': positions,
        'sequence': ['Earth', ast_name, ast_name, 'Earth'],
        'stats': {
            'total_dv_km_s': bd['total_dv'],
            'v_inf_launch_km_s': bd['v_inf_launch'],
            'v_rendezvous_km_s': bd['v_rendezvous_asteroid'],
            'v_dep_asteroid_km_s': bd['v_departure_asteroid'],
            'v_inf_arrival_earth_km_s': bd['v_inf_arrival_earth'],
            'total_duration_years': bd['total_duration_years'],
            'outbound_days': bd['outbound_days'],
            'stay_days': bd['stay_days'],
            'return_days': bd['return_days'],
        },
    }


def compare_sample_return_targets(designations: List[str],
                                   dep_window: Tuple[float, float] = (10227, 13149),
                                   verbose: bool = True) -> List[Dict]:
    """Compare sample return feasibility across multiple NEA targets."""
    from src.data.sbdb import fetch_asteroid_elements

    results = []
    for des in designations:
        if verbose:
            print(f'\n--- {des} ---', flush=True)
        try:
            elements = fetch_asteroid_elements(des)
            if not elements:
                print(f'  Not found: {des}', flush=True)
                continue
            result = optimize_sample_return(elements, dep_window=dep_window,
                                            n_arch=4, n_gen=1200, verbose=verbose)
            result['designation'] = des
            results.append(result)
        except Exception as e:
            print(f'  Failed {des}: {e}', flush=True)

    results.sort(key=lambda r: r['total_dv'])
    return results
