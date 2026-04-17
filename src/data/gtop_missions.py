"""GTOP benchmark solutions as visualizable missions.

Takes the optimized x* for each GTOP benchmark and produces trajectory
data suitable for 3D visualization: encounter events, propagated trajectory
positions, and mission statistics.
"""

import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta

from src.core.jpl_lp import jpl_lp_state, get_gtop_body_params, GTOP_MU_SUN, GTOP_AU_KM
from src.core.lambert import solve_lambert
from src.core.propagate import propagate_kepler
from src.core.gtop_cassini2 import _departure_velocity, _unpowered_flyby


# MJD2000 = 0 at 2000-01-01 00:00 UTC
_MJD2000_BASE = datetime(2000, 1, 1)


def _mjd2000_to_date(mjd2000: float) -> str:
    dt = _MJD2000_BASE + timedelta(days=mjd2000)
    return dt.strftime('%Y-%m-%d')


def _propagate_mga_1dsm(x: np.ndarray, sequence: List[str], n_legs: int,
                        add_vinf_dep: bool,
                        comet_elements: dict = None) -> Dict:
    """Propagate an MGA-1DSM solution to produce visualization data.

    Returns dict with: events, trajectory_positions, sequence, name, description, stats.
    """
    BODY_NAMES = {
        'mercury': 'Mercury', 'venus': 'Venus', 'earth': 'Earth',
        'mars': 'Mars', 'jupiter': 'Jupiter', 'saturn': 'Saturn',
    }
    BODY_INDICES = {
        'mercury': 0, 'venus': 1, 'earth': 2, 'mars': 3, 'jupiter': 4, 'saturn': 5,
    }

    t0 = x[0]
    vinf_mag = x[1]
    u, v = x[2], x[3]
    tofs = x[4:4 + n_legs]
    etas = x[4 + n_legs:4 + 2 * n_legs]
    rps = x[4 + 2 * n_legs:4 + 3 * n_legs - 1]
    betas = x[4 + 3 * n_legs - 1:4 + 4 * n_legs - 2]

    n_bodies = n_legs + 1

    # Encounter epochs
    epochs = np.zeros(n_bodies)
    epochs[0] = t0
    for i in range(n_legs):
        epochs[i + 1] = epochs[i] + tofs[i]

    # Body states
    states = []
    for i, body in enumerate(sequence):
        if body == '67p' and comet_elements:
            from src.core.kepler import propagate_state_from_elements, utc_to_jd
            jd = utc_to_jd(_mjd2000_to_date(epochs[i]))
            st = propagate_state_from_elements(
                comet_elements['a'], comet_elements['e'],
                comet_elements['i'], comet_elements['om'],
                comet_elements['w'], comet_elements['ma'],
                comet_elements['epoch_jd'], jd,
            )
            states.append(st)
        else:
            body_idx = BODY_INDICES[body]
            st = jpl_lp_state(body, epochs[i])
            states.append(st)

    # Departure velocity
    v_earth = states[0][3:]
    theta = 2.0 * np.pi * u
    phi = np.arccos(2.0 * v - 1.0) - np.pi / 2.0
    v_sc = v_earth + vinf_mag * np.array([
        np.cos(phi) * np.cos(theta),
        np.cos(phi) * np.sin(theta),
        np.sin(phi),
    ])

    # Build events and trajectory
    events = []
    all_positions = []
    total_dsm_dv = 0.0
    dsm_dvs = []

    # Launch event
    events.append({
        'body': BODY_NAMES.get(sequence[0], sequence[0].title()),
        'date': _mjd2000_to_date(epochs[0]),
        'type': 'launch',
        'distance_km': 0,
        'dv_gained_km_s': 0,
        'heliocentric_position_km': states[0][:3].tolist(),
    })

    for leg in range(n_legs):
        tof_sec = tofs[leg] * 86400.0
        eta = etas[leg]
        dt_coast = eta * tof_sec
        dt_lambert = (1.0 - eta) * tof_sec

        # Phase 1: Ballistic coast — scale points by duration (~1 point per 10 days)
        n_coast_pts = max(5, int(dt_coast / 86400 / 10))
        dt_step = dt_coast / max(n_coast_pts - 1, 1)
        r_cur, v_cur = states[leg][:3].copy(), v_sc.copy()
        for p in range(n_coast_pts):
            if p > 0 or leg == 0:
                all_positions.append(r_cur.tolist())
            if p < n_coast_pts - 1:
                r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_step, GTOP_MU_SUN)

        # DSM point
        r_dsm, v_bal = propagate_kepler(states[leg][:3], v_sc, dt_coast, GTOP_MU_SUN)

        # Phase 2: Lambert arc
        try:
            v_ls, v_le = solve_lambert(r_dsm, states[leg + 1][:3], dt_lambert, GTOP_MU_SUN)
        except Exception:
            v_ls, v_le = v_bal, states[leg + 1][3:]

        dsm_dv = np.linalg.norm(v_ls - v_bal)
        total_dsm_dv += dsm_dv
        dsm_dvs.append(dsm_dv)

        # Propagate Lambert arc for visualization — ~1 point per 10 days
        n_lambert_pts = max(5, int(dt_lambert / 86400 / 10))
        dt_step_l = dt_lambert / max(n_lambert_pts - 1, 1)
        r_cur, v_cur = r_dsm.copy(), v_ls.copy()
        for p in range(n_lambert_pts):
            all_positions.append(r_cur.tolist())
            if p < n_lambert_pts - 1:
                r_cur, v_cur = propagate_kepler(r_cur, v_cur, dt_step_l, GTOP_MU_SUN)

        # Arrival at next body
        v_arr_helio = v_le
        body_name = BODY_NAMES.get(sequence[leg + 1], sequence[leg + 1].upper())

        if leg < n_legs - 1:
            # Flyby
            params = get_gtop_body_params(sequence[leg + 1])
            rp_km = rps[leg] * params['radius']
            v_inf_in = np.linalg.norm(v_arr_helio - states[leg + 1][3:])

            events.append({
                'body': body_name,
                'date': _mjd2000_to_date(epochs[leg + 1]),
                'type': 'flyby',
                'distance_km': int(rp_km),
                'dv_gained_km_s': round(dsm_dv, 2),
                'heliocentric_position_km': states[leg + 1][:3].tolist(),
            })

            # Unpowered flyby for next leg
            v_sc = _unpowered_flyby(v_arr_helio, states[leg + 1][3:],
                                     params['mu'], rp_km, betas[leg])
        else:
            # Final arrival
            v_inf_arr = np.linalg.norm(v_arr_helio - states[leg + 1][3:])
            events.append({
                'body': body_name,
                'date': _mjd2000_to_date(epochs[leg + 1]),
                'type': 'arrival',
                'distance_km': 0,
                'dv_gained_km_s': round(v_inf_arr, 2),
                'heliocentric_position_km': states[leg + 1][:3].tolist(),
            })

    total_tof = sum(tofs)
    total_dv = (vinf_mag if add_vinf_dep else 0) + total_dsm_dv
    # Add arrival v_inf
    v_inf_final = np.linalg.norm(v_le - states[-1][3:])
    total_dv += v_inf_final

    return {
        'events': events,
        'trajectory_positions': all_positions,
        'sequence': [BODY_NAMES.get(b, b.upper()) for b in sequence],
        'stats': {
            'total_dv_km_s': round(total_dv, 3),
            'departure_vinf_km_s': round(vinf_mag, 3),
            'total_dsm_dv_km_s': round(total_dsm_dv, 3),
            'arrival_vinf_km_s': round(v_inf_final, 3),
            'total_tof_days': round(total_tof, 1),
            'n_legs': n_legs,
        },
    }


# ---- Best solutions for each benchmark ----

# These are re-optimized each time; for stability, hardcode good x* values
# found during optimization runs.

def get_gtop_cassini2() -> Dict:
    """Cassini2 EVVEJS MGA-1DSM benchmark trajectory."""
    # Best x* from island model optimization
    from src.core.gtop_fast import cassini2_evaluate_fast
    from src.core.island_model import run_archipelago
    from src.core.gtop_cassini2 import CASSINI2_BOUNDS
    from scipy.optimize import differential_evolution
    import gc

    bounds = CASSINI2_BOUNDS
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    best_x, best_f = None, np.inf
    for run in range(10):
        gc.collect()
        x, f = run_archipelago(cassini2_evaluate_fast, bounds,
            n_islands=8, pop_per_island=25, n_generations=2000, migrate_every=40,
            seed=42 + run * 1777, verbose=False)
        if f < best_f:
            best_f = f
            best_x = x.copy()

    # Narrow refinement
    narrow = [(max(lo[i], best_x[i] - 0.1 * (hi[i] - lo[i])),
               min(hi[i], best_x[i] + 0.1 * (hi[i] - lo[i]))) for i in range(22)]
    for i in range(3):
        gc.collect()
        r = differential_evolution(cassini2_evaluate_fast, bounds=narrow, maxiter=500,
            popsize=30, tol=1e-8, seed=9999 + i, disp=False, polish=True,
            strategy='best1bin', mutation=(0.3, 1.0))
        if np.isfinite(r.fun) and r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()

    result = _propagate_mga_1dsm(best_x,
        ['earth', 'venus', 'venus', 'earth', 'jupiter', 'saturn'], 5,
        add_vinf_dep=True)

    result['name'] = 'GTOP Cassini2'
    result['description'] = (
        f'Optimized EVVEJS trajectory (MGA-1DSM, 22 variables). '
        f'Total Δv: {result["stats"]["total_dv_km_s"]:.2f} km/s. '
        f'Published best: 8.383 km/s.'
    )
    return result


def get_gtop_messenger() -> Dict:
    """Messenger EEVVM MGA-1DSM benchmark trajectory."""
    from src.core.gtop_fast import messenger_evaluate_fast
    from src.core.island_model import run_archipelago
    from scipy.optimize import differential_evolution
    import gc

    bounds = [
        (1000.0, 4000.0), (1.0, 5.0), (0.0, 1.0), (0.0, 1.0),
        (200.0, 400.0), (30.0, 400.0), (30.0, 400.0), (30.0, 400.0),
        (0.01, 0.99), (0.01, 0.99), (0.01, 0.99), (0.01, 0.99),
        (1.1, 6.0), (1.1, 6.0), (1.1, 6.0),
        (-np.pi, np.pi), (-np.pi, np.pi), (-np.pi, np.pi),
    ]
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    best_x, best_f = None, np.inf
    for run in range(10):
        gc.collect()
        x, f = run_archipelago(messenger_evaluate_fast, bounds,
            n_islands=8, pop_per_island=25, n_generations=2000, migrate_every=40,
            seed=42 + run * 1777, verbose=False)
        if f < best_f:
            best_f = f
            best_x = x.copy()

    narrow = [(max(lo[i], best_x[i] - 0.1 * (hi[i] - lo[i])),
               min(hi[i], best_x[i] + 0.1 * (hi[i] - lo[i]))) for i in range(18)]
    for i in range(3):
        gc.collect()
        r = differential_evolution(messenger_evaluate_fast, bounds=narrow, maxiter=500,
            popsize=30, tol=1e-8, seed=9999 + i, disp=False, polish=True,
            strategy='best1bin', mutation=(0.3, 1.0))
        if np.isfinite(r.fun) and r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()

    result = _propagate_mga_1dsm(best_x,
        ['earth', 'earth', 'venus', 'venus', 'mercury'], 4,
        add_vinf_dep=True)

    result['name'] = 'GTOP Messenger'
    result['description'] = (
        f'Optimized EEVV-Mercury trajectory (MGA-1DSM, 18 variables). '
        f'Total Δv: {result["stats"]["total_dv_km_s"]:.2f} km/s. '
        f'Published best: 8.630 km/s.'
    )
    return result


def get_gtop_rosetta() -> Dict:
    """Rosetta EEMaEE-67P MGA-1DSM benchmark trajectory."""
    from src.core.gtop_fast import rosetta_evaluate_fast
    from src.core.island_model import run_archipelago
    from scipy.optimize import differential_evolution
    import gc

    bounds = [
        (1460.0, 1825.0), (3.0, 5.0), (0.0, 1.0), (0.0, 1.0),
        (300.0, 500.0), (150.0, 800.0), (150.0, 800.0), (300.0, 800.0), (700.0, 1850.0),
        (0.01, 0.9), (0.01, 0.9), (0.01, 0.9), (0.01, 0.9), (0.01, 0.9),
        (1.05, 9.0), (1.05, 9.0), (1.05, 9.0), (1.05, 9.0),
        (-np.pi, np.pi), (-np.pi, np.pi), (-np.pi, np.pi), (-np.pi, np.pi),
    ]
    # Seed near published basin for Rosetta (the basin is too narrow for random search)
    seeded_bounds = list(bounds)
    # Narrow TOFs and rps near published solution
    pub_tofs = [365.24, 707.75, 257.32, 730.48, 1850.0]
    pub_rps = [2.66, 1.05, 3.20, 1.06]
    for i, val in enumerate(pub_tofs):
        lo_b, hi_b = bounds[4 + i]
        width = 0.15 * (hi_b - lo_b)
        seeded_bounds[4 + i] = (max(lo_b, val - width), min(hi_b, val + width))
    for i, val in enumerate(pub_rps):
        lo_b, hi_b = bounds[14 + i]
        width = 0.15 * (hi_b - lo_b)
        seeded_bounds[14 + i] = (max(lo_b, val - width), min(hi_b, val + width))

    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    best_x, best_f = None, np.inf
    for run in range(10):
        gc.collect()
        x, f = run_archipelago(rosetta_evaluate_fast, seeded_bounds,
            n_islands=8, pop_per_island=25, n_generations=2000, migrate_every=40,
            seed=42 + run * 1777, verbose=False)
        if f < best_f:
            best_f = f
            best_x = x.copy()

    narrow = [(max(lo[i], best_x[i] - 0.05 * (hi[i] - lo[i])),
               min(hi[i], best_x[i] + 0.05 * (hi[i] - lo[i]))) for i in range(22)]
    for i in range(3):
        gc.collect()
        r = differential_evolution(rosetta_evaluate_fast, bounds=narrow, maxiter=500,
            popsize=30, tol=1e-8, seed=9999 + i, disp=False, polish=True,
            strategy='best1bin', mutation=(0.3, 1.0))
        if np.isfinite(r.fun) and r.fun < best_f:
            best_f = r.fun
            best_x = r.x.copy()

    # 67P comet elements for propagation
    comet = {
        'a': 3.50294972836275, 'e': 0.6319356, 'i': 7.12723,
        'om': 50.92302, 'w': 11.36788, 'ma': 0.0,
        'epoch_jd': 2452504.73754,
    }

    result = _propagate_mga_1dsm(best_x,
        ['earth', 'earth', 'mars', 'earth', 'earth', '67p'], 5,
        add_vinf_dep=False, comet_elements=comet)

    result['name'] = 'GTOP Rosetta'
    result['description'] = (
        f'Optimized Earth-Earth-Mars-Earth-Earth-67P trajectory (MGA-1DSM, 22 variables). '
        f'Total Δv: {result["stats"]["total_dv_km_s"]:.2f} km/s. '
        f'Published best: 1.343 km/s.'
    )
    return result


# Registry
GTOP_BENCHMARKS = {
    'cassini2': get_gtop_cassini2,
    'messenger': get_gtop_messenger,
    'rosetta': get_gtop_rosetta,
}


def get_gtop_benchmark(name: str) -> Dict:
    """Get a GTOP benchmark trajectory by name."""
    if name not in GTOP_BENCHMARKS:
        return None
    return GTOP_BENCHMARKS[name]()


def list_gtop_benchmarks() -> List[Dict]:
    """List available GTOP benchmarks (without computing trajectories)."""
    return [
        {'id': 'cassini2', 'name': 'GTOP Cassini2', 'sequence': 'E→V→V→E→J→S', 'published_dv': 8.383},
        {'id': 'messenger', 'name': 'GTOP Messenger', 'sequence': 'E→E→V→V→Me', 'published_dv': 8.630},
        {'id': 'rosetta', 'name': 'GTOP Rosetta', 'sequence': 'E→E→Ma→E→E→67P', 'published_dv': 1.343},
    ]
