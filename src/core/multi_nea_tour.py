"""Multi-NEA Tour — visit multiple near-Earth asteroids in one mission.

Traveling salesman problem in 4D (position + time) with rendezvous at each target.

For a 2-asteroid tour (Earth → A1 → A2 → Earth):
  Decision variables (6): t0, T1, stay1, T2, stay2, T3
  Cost: Σ (v_inf at each rendezvous boundary)
"""

import numpy as np
import gc
from typing import Dict, List, Tuple, Optional
from scipy.optimize import differential_evolution

from .jpl_lp import jpl_lp_state, GTOP_MU_SUN
from .lambert import solve_lambert
from .sample_return import _asteroid_state
from .island_model import run_archipelago


def make_2nea_evaluator(ast1: Dict, ast2: Dict):
    """Build an evaluator for a 2-asteroid tour: E → A1 → A2 → E."""
    PENALTY = 1e6

    def evaluate(x):
        t0, T1, stay1, T2, stay2, T3 = x[0], x[1], x[2], x[3], x[4], x[5]

        t_arr1 = t0 + T1
        t_dep1 = t_arr1 + stay1
        t_arr2 = t_dep1 + T2
        t_dep2 = t_arr2 + stay2
        t_ret = t_dep2 + T3

        try:
            r_e0 = jpl_lp_state('earth', t0)
            r_a1_arr = _asteroid_state(ast1, t_arr1)
            r_a1_dep = _asteroid_state(ast1, t_dep1)
            r_a2_arr = _asteroid_state(ast2, t_arr2)
            r_a2_dep = _asteroid_state(ast2, t_dep2)
            r_e1 = jpl_lp_state('earth', t_ret)

            v1_1, v2_1 = solve_lambert(r_e0[:3], r_a1_arr[:3], T1 * 86400, GTOP_MU_SUN)
            v1_2, v2_2 = solve_lambert(r_a1_dep[:3], r_a2_arr[:3], T2 * 86400, GTOP_MU_SUN)
            v1_3, v2_3 = solve_lambert(r_a2_dep[:3], r_e1[:3], T3 * 86400, GTOP_MU_SUN)
        except Exception:
            return PENALTY

        for v in (v1_1, v2_1, v1_2, v2_2, v1_3, v2_3):
            if not np.all(np.isfinite(v)):
                return PENALTY

        dv = (np.linalg.norm(v1_1 - r_e0[3:]) +      # launch vinf
              np.linalg.norm(v2_1 - r_a1_arr[3:]) + # arrive at A1
              np.linalg.norm(v1_2 - r_a1_dep[3:]) + # depart A1
              np.linalg.norm(v2_2 - r_a2_arr[3:]) + # arrive at A2
              np.linalg.norm(v1_3 - r_a2_dep[3:]) + # depart A2
              np.linalg.norm(v2_3 - r_e1[3:]))      # arrive at Earth

        return float(dv) if np.isfinite(dv) else PENALTY

    return evaluate


def optimize_2nea_tour(ast1_elements: Dict, ast2_elements: Dict,
                      dep_window: Tuple[float, float] = (10227, 13149),
                      tof_range: Tuple[float, float] = (100, 800),
                      stay_range: Tuple[float, float] = (30, 300),
                      n_arch: int = 4, n_gen: int = 1200,
                      verbose: bool = True) -> Dict:
    """Optimize a 2-asteroid rendezvous tour."""
    evaluate = make_2nea_evaluator(ast1_elements, ast2_elements)
    bounds = [dep_window, tof_range, stay_range, tof_range, stay_range, tof_range]
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
            print(f'  Arch {run + 1}/{n_arch}: {f:.3f}{" ***BEST***" if f == best_f else ""}', flush=True)

    narrow = [(max(lo[i], best_x[i] - 0.1 * (hi[i] - lo[i])),
               min(hi[i], best_x[i] + 0.1 * (hi[i] - lo[i]))) for i in range(6)]
    for i in range(3):
        gc.collect()
        r = differential_evolution(evaluate, bounds=narrow, maxiter=500, popsize=30,
            tol=1e-8, seed=9999 + i, disp=False, polish=True,
            strategy='best1bin', mutation=(0.3, 1.0))
        if np.isfinite(r.fun) and r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()

    return _tour_2nea_breakdown(best_x, ast1_elements, ast2_elements)


def _tour_2nea_breakdown(x, ast1, ast2):
    from datetime import datetime, timedelta

    t0, T1, stay1, T2, stay2, T3 = float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])
    t_arr1 = t0 + T1
    t_dep1 = t_arr1 + stay1
    t_arr2 = t_dep1 + T2
    t_dep2 = t_arr2 + stay2
    t_ret = t_dep2 + T3

    r_e0 = jpl_lp_state('earth', t0)
    r_a1_arr = _asteroid_state(ast1, t_arr1)
    r_a1_dep = _asteroid_state(ast1, t_dep1)
    r_a2_arr = _asteroid_state(ast2, t_arr2)
    r_a2_dep = _asteroid_state(ast2, t_dep2)
    r_e1 = jpl_lp_state('earth', t_ret)

    v1_1, v2_1 = solve_lambert(r_e0[:3], r_a1_arr[:3], T1 * 86400, GTOP_MU_SUN)
    v1_2, v2_2 = solve_lambert(r_a1_dep[:3], r_a2_arr[:3], T2 * 86400, GTOP_MU_SUN)
    v1_3, v2_3 = solve_lambert(r_a2_dep[:3], r_e1[:3], T3 * 86400, GTOP_MU_SUN)

    vinfs = {
        'launch': float(np.linalg.norm(v1_1 - r_e0[3:])),
        'arrive_a1': float(np.linalg.norm(v2_1 - r_a1_arr[3:])),
        'depart_a1': float(np.linalg.norm(v1_2 - r_a1_dep[3:])),
        'arrive_a2': float(np.linalg.norm(v2_2 - r_a2_arr[3:])),
        'depart_a2': float(np.linalg.norm(v1_3 - r_a2_dep[3:])),
        'arrive_earth': float(np.linalg.norm(v2_3 - r_e1[3:])),
    }

    base = datetime(2000, 1, 1)

    def ast_name(el):
        n = el.get('name', '').split('(')[0].strip()
        return n if n else el.get('des', 'Asteroid')

    return {
        'ast1_name': ast_name(ast1),
        'ast2_name': ast_name(ast2),
        'total_dv': sum(vinfs.values()),
        'vinfs': vinfs,
        'departure_date': (base + timedelta(days=t0)).strftime('%Y-%m-%d'),
        'arr_a1_date': (base + timedelta(days=t_arr1)).strftime('%Y-%m-%d'),
        'dep_a1_date': (base + timedelta(days=t_dep1)).strftime('%Y-%m-%d'),
        'arr_a2_date': (base + timedelta(days=t_arr2)).strftime('%Y-%m-%d'),
        'dep_a2_date': (base + timedelta(days=t_dep2)).strftime('%Y-%m-%d'),
        'return_date': (base + timedelta(days=t_ret)).strftime('%Y-%m-%d'),
        'total_duration_years': float((T1 + stay1 + T2 + stay2 + T3) / 365.25),
        'x': x.tolist(),
    }


def propagate_2nea_mission(x, ast1, ast2) -> Dict:
    """Full trajectory propagation for visualization."""
    from .propagate import propagate_kepler
    from datetime import datetime, timedelta

    t0, T1, stay1, T2, stay2, T3 = float(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])
    t_arr1 = t0 + T1
    t_dep1 = t_arr1 + stay1
    t_arr2 = t_dep1 + T2
    t_dep2 = t_arr2 + stay2
    t_ret = t_dep2 + T3

    r_e0 = jpl_lp_state('earth', t0)
    r_a1_arr = _asteroid_state(ast1, t_arr1)
    r_a1_dep = _asteroid_state(ast1, t_dep1)
    r_a2_arr = _asteroid_state(ast2, t_arr2)
    r_a2_dep = _asteroid_state(ast2, t_dep2)
    r_e1 = jpl_lp_state('earth', t_ret)

    v1_1, v2_1 = solve_lambert(r_e0[:3], r_a1_arr[:3], T1 * 86400, GTOP_MU_SUN)
    v1_2, v2_2 = solve_lambert(r_a1_dep[:3], r_a2_arr[:3], T2 * 86400, GTOP_MU_SUN)
    v1_3, v2_3 = solve_lambert(r_a2_dep[:3], r_e1[:3], T3 * 86400, GTOP_MU_SUN)

    positions = []

    def prop_leg(r_start, v_start, duration_days):
        n = max(40, int(duration_days / 2))
        dt_step = duration_days * 86400.0 / max(n - 1, 1)
        r, v = r_start.copy(), v_start.copy()
        pts = []
        for p in range(n):
            pts.append(r.tolist())
            if p < n - 1:
                r, v = propagate_kepler(r, v, dt_step, GTOP_MU_SUN)
        return pts

    def follow_asteroid(el, t_start_mjd, duration_days):
        n = max(10, int(duration_days / 10))
        pts = []
        for p in range(n):
            frac = p / max(n - 1, 1)
            t = t_start_mjd + frac * duration_days
            pts.append(_asteroid_state(el, t)[:3].tolist())
        return pts

    positions.extend(prop_leg(r_e0[:3], v1_1, T1))
    positions.extend(follow_asteroid(ast1, t_arr1, stay1))
    positions.extend(prop_leg(r_a1_dep[:3], v1_2, T2))
    positions.extend(follow_asteroid(ast2, t_arr2, stay2))
    positions.extend(prop_leg(r_a2_dep[:3], v1_3, T3))

    def name(el):
        n = el.get('name', '').split('(')[0].strip()
        return n if n else el.get('des', 'Asteroid')
    n1, n2 = name(ast1), name(ast2)

    base = datetime(2000, 1, 1)
    def fmt(d): return (base + timedelta(days=d)).strftime('%Y-%m-%d')

    events = [
        {'body': 'Earth', 'date': fmt(t0), 'type': 'launch',
         'distance_km': 0, 'dv_gained_km_s': 0,
         'heliocentric_position_km': r_e0[:3].tolist()},
        {'body': n1, 'date': fmt(t_arr1), 'type': 'flyby',
         'distance_km': 0,
         'dv_gained_km_s': round(float(np.linalg.norm(v2_1 - r_a1_arr[3:])), 2),
         'heliocentric_position_km': r_a1_arr[:3].tolist()},
        {'body': n1, 'date': fmt(t_dep1), 'type': 'flyby',
         'distance_km': 0,
         'dv_gained_km_s': round(float(np.linalg.norm(v1_2 - r_a1_dep[3:])), 2),
         'heliocentric_position_km': r_a1_dep[:3].tolist()},
        {'body': n2, 'date': fmt(t_arr2), 'type': 'flyby',
         'distance_km': 0,
         'dv_gained_km_s': round(float(np.linalg.norm(v2_2 - r_a2_arr[3:])), 2),
         'heliocentric_position_km': r_a2_arr[:3].tolist()},
        {'body': n2, 'date': fmt(t_dep2), 'type': 'flyby',
         'distance_km': 0,
         'dv_gained_km_s': round(float(np.linalg.norm(v1_3 - r_a2_dep[3:])), 2),
         'heliocentric_position_km': r_a2_dep[:3].tolist()},
        {'body': 'Earth', 'date': fmt(t_ret), 'type': 'arrival',
         'distance_km': 0,
         'dv_gained_km_s': round(float(np.linalg.norm(v2_3 - r_e1[3:])), 2),
         'heliocentric_position_km': r_e1[:3].tolist()},
    ]

    bd = _tour_2nea_breakdown(x, ast1, ast2)
    return {
        'events': events,
        'trajectory_positions': positions,
        'sequence': ['Earth', n1, n1, n2, n2, 'Earth'],
        'stats': {
            'total_dv_km_s': bd['total_dv'],
            'launch_vinf_km_s': bd['vinfs']['launch'],
            'arrive_a1_vinf_km_s': bd['vinfs']['arrive_a1'],
            'depart_a1_vinf_km_s': bd['vinfs']['depart_a1'],
            'arrive_a2_vinf_km_s': bd['vinfs']['arrive_a2'],
            'depart_a2_vinf_km_s': bd['vinfs']['depart_a2'],
            'arrive_earth_vinf_km_s': bd['vinfs']['arrive_earth'],
            'total_duration_years': bd['total_duration_years'],
        },
    }
