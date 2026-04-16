"""Novel mission design — arbitrary MGA-1DSM trajectory optimization.

Uses SPICE ephemeris (real planet positions) and the C evaluator for speed.
Supports any planetary sequence with configurable bounds.
"""

import numpy as np
from typing import Dict, List, Tuple
import gc

from .jpl_lp import GTOP_MU_SUN
from .island_model import run_archipelago


def _build_c_evaluator(sequence: List[str], add_vinf_dep: bool = True):
    """Build a Python evaluate function for an arbitrary MGA-1DSM sequence.

    Uses the JPL LP analytical ephemeris and the same physics as the GTOP
    benchmarks, but with arbitrary sequences and bounds.
    """
    from .jpl_lp import jpl_lp_state, get_gtop_body_params
    from .lambert import solve_lambert
    from .propagate import propagate_kepler
    from .gtop_cassini2 import _unpowered_flyby

    n_bodies = len(sequence)
    n_legs = n_bodies - 1
    mu_sun = GTOP_MU_SUN
    PENALTY = 1e6

    # Pre-lookup body params for flybys
    flyby_params = []
    for i in range(1, n_bodies - 1):
        flyby_params.append(get_gtop_body_params(sequence[i]))

    def evaluate(x):
        """x layout: [t0, Vinf, u, v, T1..Tn, eta1..etan, rp1..rp(n-1), beta1..beta(n-1)]"""
        t0 = x[0]
        vinf_mag = x[1]
        u, v = x[2], x[3]
        tofs = x[4:4 + n_legs]
        etas = x[4 + n_legs:4 + 2 * n_legs]
        rps = x[4 + 2 * n_legs:4 + 3 * n_legs - 1]
        betas = x[4 + 3 * n_legs - 1:4 + 4 * n_legs - 2]

        # Epochs
        epochs = np.zeros(n_bodies)
        epochs[0] = t0
        for i in range(n_legs):
            epochs[i + 1] = epochs[i] + tofs[i]

        # Body states
        states = []
        try:
            for i, body in enumerate(sequence):
                states.append(jpl_lp_state(body, epochs[i]))
        except Exception:
            return PENALTY

        # Departure
        theta = 2.0 * np.pi * u
        phi = np.arccos(2.0 * v - 1.0) - np.pi / 2.0
        v_sc = states[0][3:].copy()
        v_sc[0] += vinf_mag * np.cos(phi) * np.cos(theta)
        v_sc[1] += vinf_mag * np.cos(phi) * np.sin(theta)
        v_sc[2] += vinf_mag * np.sin(phi)

        total_dv = vinf_mag if add_vinf_dep else 0.0

        for leg in range(n_legs):
            tof_sec = tofs[leg] * 86400.0
            eta = etas[leg]
            dt_coast = eta * tof_sec
            dt_lambert = (1.0 - eta) * tof_sec
            if dt_lambert < 1.0:
                return PENALTY

            try:
                r_dsm, v_bal = propagate_kepler(states[leg][:3], v_sc, dt_coast, mu_sun)
            except Exception:
                return PENALTY
            if not np.all(np.isfinite(r_dsm)):
                return PENALTY

            try:
                v_ls, v_le = solve_lambert(r_dsm, states[leg + 1][:3], dt_lambert, mu_sun)
            except Exception:
                return PENALTY
            if not np.all(np.isfinite(v_ls)):
                return PENALTY

            dsm = np.linalg.norm(v_ls - v_bal)
            if not np.isfinite(dsm):
                return PENALTY
            total_dv += dsm

            if leg < n_legs - 1:
                params = flyby_params[leg]
                rp_km = rps[leg] * params['radius']
                v_sc = _unpowered_flyby(v_le, states[leg + 1][3:],
                                         params['mu'], rp_km, betas[leg])
                if not np.all(np.isfinite(v_sc)):
                    return PENALTY
            else:
                vinf_arr = np.linalg.norm(v_le - states[n_bodies - 1][3:])
                total_dv += vinf_arr

        return total_dv if np.isfinite(total_dv) else PENALTY

    return evaluate


def _build_bounds(sequence: List[str], dep_window: Tuple[float, float],
                  tof_ranges: List[Tuple[float, float]],
                  vinf_range: Tuple[float, float] = (1.0, 7.0)) -> list:
    """Build MGA-1DSM bounds for an arbitrary sequence."""
    n_legs = len(sequence) - 1

    # Default flyby rp ranges (in body radii)
    SAFE_FACTORS = {
        'mercury': (1.1, 6), 'venus': (1.1, 6), 'earth': (1.1, 6),
        'mars': (1.1, 6), 'jupiter': (1.7, 100), 'saturn': (1.1, 50),
        'uranus': (1.1, 20), 'neptune': (1.1, 20),
    }

    bounds = [
        dep_window,                     # t0 (MJD2000)
        vinf_range,                     # Vinf (km/s)
        (0.0, 1.0),                     # u
        (0.0, 1.0),                     # v
    ]

    # TOFs
    for i in range(n_legs):
        bounds.append(tof_ranges[i])

    # Etas
    for _ in range(n_legs):
        bounds.append((0.01, 0.9))

    # Flyby rps (n_legs - 1 flybys, excluding departure and arrival)
    for i in range(1, len(sequence) - 1):
        lo, hi = SAFE_FACTORS.get(sequence[i], (1.1, 10))
        bounds.append((lo, hi))

    # Betas
    for _ in range(1, len(sequence) - 1):
        bounds.append((-np.pi, np.pi))

    return bounds


def optimize_sequence(sequence: List[str], dep_window: Tuple[float, float],
                      tof_ranges: List[Tuple[float, float]],
                      vinf_range: Tuple[float, float] = (1.0, 7.0),
                      n_arch: int = 15, n_gen: int = 2000,
                      add_vinf_dep: bool = True,
                      verbose: bool = True) -> Dict:
    """Optimize an MGA-1DSM trajectory for an arbitrary planetary sequence.

    Uses the C generic evaluator for ~100× speedup over Python.
    """
    from scipy.optimize import differential_evolution
    from .gtop_fast import make_generic_evaluator

    evaluate = make_generic_evaluator(sequence, add_vinf_dep)
    bounds = _build_bounds(sequence, dep_window, tof_ranges, vinf_range)
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])
    n_legs = len(sequence) - 1

    best_x, best_f = None, np.inf

    for run in range(n_arch):
        gc.collect()
        x, f = run_archipelago(evaluate, bounds,
            n_islands=8, pop_per_island=25, n_generations=n_gen, migrate_every=40,
            seed=42 + run * 1777, verbose=False)
        tag = ''
        if f < best_f:
            best_f = f
            best_x = x.copy()
            tag = ' ***BEST***'
        if verbose and ((run + 1) % 5 == 0 or tag):
            print(f'  Arch {run + 1:2d}/{n_arch}: {f:.4f}{tag}', flush=True)

    # Narrow DE refinement
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

    # Extract stats
    tofs = best_x[4:4 + n_legs]
    total_tof = sum(tofs)

    # Convert t0 from MJD2000 to date
    from datetime import datetime, timedelta
    base = datetime(2000, 1, 1)
    dep_date = base + timedelta(days=best_x[0])
    arr_date = base + timedelta(days=best_x[0] + total_tof)

    return {
        'sequence': sequence,
        'total_dv': float(best_f),
        'departure_vinf': float(best_x[1]),
        'c3_launch': float(best_x[1] ** 2),
        'total_tof_days': float(total_tof),
        'total_tof_years': float(total_tof / 365.25),
        'departure_date': dep_date.strftime('%Y-%m-%d'),
        'arrival_date': arr_date.strftime('%Y-%m-%d'),
        'leg_tofs_days': [float(t) for t in tofs],
        'x': best_x.tolist(),
        'n_vars': len(bounds),
    }


def modern_grand_tour(verbose: bool = True) -> Dict:
    """Find the best outer solar system tour with 2028-2035 launch windows.

    Tests multiple sequences and returns the best option along with
    a comparison table.
    """
    # Departure window: 2028-2035 (MJD2000 = 10227 to 12784)
    dep_window = (10227.0, 12784.0)

    # Candidate sequences — realistic outer planet tours
    candidates = [
        {
            'name': 'Jupiter-Saturn (VEJS)',
            'sequence': ['earth', 'venus', 'earth', 'jupiter', 'saturn'],
            'tof_ranges': [(100, 400), (200, 600), (400, 1600), (800, 3000)],
        },
        {
            'name': 'Jupiter-Saturn (EJS direct)',
            'sequence': ['earth', 'jupiter', 'saturn'],
            'tof_ranges': [(400, 2500), (800, 3000)],
        },
        {
            'name': 'Jupiter-Saturn (EEJS)',
            'sequence': ['earth', 'earth', 'jupiter', 'saturn'],
            'tof_ranges': [(200, 600), (400, 2000), (800, 3000)],
        },
        {
            'name': 'Jupiter-Saturn-Uranus (VEJSU)',
            'sequence': ['earth', 'venus', 'earth', 'jupiter', 'saturn', 'uranus'],
            'tof_ranges': [(100, 400), (200, 600), (400, 1600), (800, 2500), (1000, 5000)],
        },
        {
            'name': 'Jupiter-Saturn-Neptune (EJSN)',
            'sequence': ['earth', 'earth', 'jupiter', 'saturn', 'neptune'],
            'tof_ranges': [(200, 600), (400, 2000), (800, 2500), (2000, 8000)],
        },
        {
            'name': 'Jupiter only (VEJ)',
            'sequence': ['earth', 'venus', 'earth', 'jupiter'],
            'tof_ranges': [(100, 400), (200, 600), (400, 2000)],
            'vinf_range': (1.0, 6.0),
        },
    ]

    results = []
    if verbose:
        print('='*60, flush=True)
        print('Modern Grand Tour — Outer Solar System (2028–2035)', flush=True)
        print('='*60, flush=True)

    for cand in candidates:
        if verbose:
            print(f'\n--- {cand["name"]} ---', flush=True)
        try:
            result = optimize_sequence(
                cand['sequence'],
                dep_window,
                cand['tof_ranges'],
                vinf_range=cand.get('vinf_range', (1.0, 7.0)),
                n_arch=10,
                n_gen=2000,
                verbose=verbose,
            )
            result['name'] = cand['name']
            results.append(result)
            if verbose:
                print(f'  Result: {result["total_dv"]:.2f} km/s, '
                      f'TOF={result["total_tof_years"]:.1f} yr, '
                      f'C3={result["c3_launch"]:.1f}, '
                      f'dep={result["departure_date"]}', flush=True)
        except Exception as e:
            if verbose:
                print(f'  Failed: {e}', flush=True)

    results.sort(key=lambda r: r['total_dv'])

    if verbose:
        print(f'\n{"="*60}', flush=True)
        print('COMPARISON TABLE', flush=True)
        print(f'{"Sequence":<35s} {"Δv km/s":>8s} {"TOF yr":>7s} {"C3":>6s} {"Depart":>12s}', flush=True)
        print('-' * 72, flush=True)
        for r in results:
            seq_str = '→'.join([s[0].upper() for s in r['sequence']])
            print(f'{r["name"]:<35s} {r["total_dv"]:8.2f} {r["total_tof_years"]:7.1f} '
                  f'{r["c3_launch"]:6.1f} {r["departure_date"]:>12s}', flush=True)

    return {
        'best': results[0] if results else None,
        'all_results': results,
    }
