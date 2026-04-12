"""GTOP Cassini2 benchmark — MGA-1DSM formulation.

Sequence: E-V-V-E-J-S (same as Cassini1, but with deep space maneuvers)
22 decision variables: t0, v_inf, u, v, T1-T5, eta1-eta5, rp1-rp4, beta1-beta4

The MGA-1DSM model allows one impulsive deep-space maneuver per leg.
For each leg, the spacecraft coasts ballistically for eta*T days, then
executes a DSM to redirect onto a Lambert arc for the remaining (1-eta)*T days.

Flybys are unpowered (v_inf magnitude conserved) with rp and beta as
decision variables that control the deflection geometry.

Reference: https://www.esa.int/gsp/ACT/projects/gtop/cassini2/
Published best: 8.383 km/s
"""

import numpy as np
from scipy.optimize import differential_evolution
from typing import Dict, Tuple
from .lambert import solve_lambert
from .propagate import propagate_kepler
from .flyby import compute_flyby
from .jpl_lp import jpl_lp_state, get_gtop_body_params, GTOP_MU_SUN

CASSINI2_SEQUENCE = ['earth', 'venus', 'venus', 'earth', 'jupiter', 'saturn']

# Bounds: [t0, Vinf, u, v, T1-T5, eta1-eta5, rp1-rp4, beta1-beta4]
CASSINI2_BOUNDS = [
    (-1000.0, 0.0),       # t0 (MJD2000)
    (3.0, 5.0),           # Vinf departure (km/s)
    (0.0, 1.0),           # u (direction param)
    (0.0, 1.0),           # v (direction param)
    (100.0, 400.0),       # T1: E→V
    (100.0, 500.0),       # T2: V→V
    (30.0, 300.0),        # T3: V→E
    (400.0, 1600.0),      # T4: E→J
    (800.0, 2200.0),      # T5: J→S
    (0.01, 0.9),          # eta1
    (0.01, 0.9),          # eta2
    (0.01, 0.9),          # eta3
    (0.01, 0.9),          # eta4
    (0.01, 0.9),          # eta5
    (1.05, 6.0),          # rp1 (Venus radii)
    (1.05, 6.0),          # rp2 (Venus radii)
    (1.15, 6.5),          # rp3 (Earth radii)
    (1.7, 291.0),         # rp4 (Jupiter radii)
    (-np.pi, np.pi),      # beta1
    (-np.pi, np.pi),      # beta2
    (-np.pi, np.pi),      # beta3
    (-np.pi, np.pi),      # beta4
]


def _departure_velocity(v_planet: np.ndarray, vinf_mag: float,
                        u: float, v: float) -> np.ndarray:
    """Compute departure velocity from (u, v) direction parameters.

    The v_inf direction is parameterized by (u, v) mapped to spherical
    coordinates in the ECLIPTIC J2000 frame (matches pagmo MGA_DSM).
    """
    theta = 2.0 * np.pi * u
    phi = np.arccos(2.0 * v - 1.0) - np.pi / 2.0

    v_inf = vinf_mag * np.array([
        np.cos(phi) * np.cos(theta),
        np.cos(phi) * np.sin(theta),
        np.sin(phi),
    ])

    return v_planet + v_inf


def _unpowered_flyby(v_in_helio: np.ndarray, v_planet: np.ndarray,
                     mu_body: float, rp: float,
                     beta: float) -> np.ndarray:
    """Compute outgoing heliocentric velocity after an unpowered flyby.

    Uses the exact pykep fb_prop formulation:
    - i_hat = unit(v_inf_in)
    - k_hat = unit(v_inf_in × v_planet)  [reference plane from planet velocity]
    - j_hat = k_hat × i_hat
    - v_inf_out = |v_inf| * (cos(δ)*i + sin(δ)*sin(β)*j + sin(δ)*cos(β)*k)

    This ensures the beta parameter maps to the same physical direction as pykep.
    """
    v_inf_in = v_in_helio - v_planet
    v_inf_mag = np.linalg.norm(v_inf_in)

    if v_inf_mag < 1e-10:
        return v_in_helio.copy()

    # Deflection angle
    e = 1.0 + rp * v_inf_mag ** 2 / mu_body
    delta = 2.0 * np.arcsin(min(1.0 / e, 1.0))

    # Build local frame (pykep convention)
    i_hat = v_inf_in / v_inf_mag

    k_hat = np.cross(i_hat, v_planet)
    k_norm = np.linalg.norm(k_hat)
    if k_norm < 1e-10:
        # v_inf parallel to v_planet — use ecliptic pole as fallback
        k_hat = np.cross(i_hat, np.array([0.0, 0.0, 1.0]))
        k_norm = np.linalg.norm(k_hat)
    k_hat = k_hat / k_norm

    j_hat = np.cross(k_hat, i_hat)

    # Outgoing v_inf direction
    v_inf_out = v_inf_mag * (
        np.cos(delta) * i_hat +
        np.sin(delta) * np.sin(beta) * j_hat +
        np.sin(delta) * np.cos(beta) * k_hat
    )

    return v_planet + v_inf_out


def cassini2_evaluate(x: np.ndarray) -> float:
    """Evaluate the GTOP Cassini2 MGA-1DSM objective function.

    Decision variables (22):
        x[0]: t0 (MJD2000)
        x[1]: Vinf departure magnitude (km/s)
        x[2]: u (v_inf direction)
        x[3]: v (v_inf direction)
        x[4:9]: T1-T5 (leg TOFs in days)
        x[9:14]: eta1-eta5 (DSM fractions)
        x[14:18]: rp1-rp4 (flyby periapsis in body radii)
        x[18:22]: beta1-beta4 (flyby plane rotation in rad)

    Returns:
        Total delta-v (km/s) = Vinf_dep + Σ(DSM) + Vinf_arrival
    """
    PENALTY = 1e6

    t0_mjd = x[0]
    vinf_mag = x[1]
    u, v = x[2], x[3]
    tofs_days = x[4:9]
    etas = x[9:14]
    rps_radii = x[14:18]
    betas = x[18:22]

    sequence = CASSINI2_SEQUENCE

    # Encounter epochs (MJD2000)
    epochs_mjd = np.zeros(6)
    epochs_mjd[0] = t0_mjd
    for i in range(5):
        epochs_mjd[i + 1] = epochs_mjd[i] + tofs_days[i]

    # Get planet states from analytical ephemeris
    try:
        states = [jpl_lp_state(body, epochs_mjd[i]) for i, body in enumerate(sequence)]
    except Exception:
        return PENALTY

    # Departure: compute initial spacecraft velocity
    v_earth = states[0][3:]
    v_sc = _departure_velocity(v_earth, vinf_mag, u, v)

    total_dv = vinf_mag  # departure cost

    # Process each leg
    for leg in range(5):
        tof_sec = tofs_days[leg] * 86400.0
        eta = etas[leg]

        r_dep = states[leg][:3]
        r_arr = states[leg + 1][:3]

        # Phase 1: Ballistic coast for eta * TOF
        dt_coast = eta * tof_sec
        try:
            r_dsm, v_ballistic = propagate_kepler(r_dep, v_sc, dt_coast, GTOP_MU_SUN)
        except Exception:
            return PENALTY

        if not np.all(np.isfinite(r_dsm)) or not np.all(np.isfinite(v_ballistic)):
            return PENALTY

        # Phase 2: Lambert from DSM point to next body for (1-eta) * TOF
        dt_lambert = (1.0 - eta) * tof_sec
        if dt_lambert < 1.0:
            return PENALTY

        try:
            v_lambert_start, v_lambert_end = solve_lambert(
                r_dsm, r_arr, dt_lambert, GTOP_MU_SUN
            )
        except (ValueError, RuntimeError):
            return PENALTY

        if not np.all(np.isfinite(v_lambert_start)) or not np.all(np.isfinite(v_lambert_end)):
            return PENALTY

        # DSM cost
        dsm_dv = np.linalg.norm(v_lambert_start - v_ballistic)
        if not np.isfinite(dsm_dv):
            return PENALTY
        total_dv += dsm_dv

        v_arr_helio = v_lambert_end

        # Flyby at next body (if not final)
        if leg < 4:
            flyby_body = sequence[leg + 1]
            params = get_gtop_body_params(flyby_body)
            rp_km = rps_radii[leg] * params['radius']
            beta = betas[leg]
            v_sc = _unpowered_flyby(v_arr_helio, states[leg + 1][3:],
                                     params['mu'], rp_km, beta)
            if not np.all(np.isfinite(v_sc)):
                return PENALTY
        else:
            v_saturn = states[5][3:]
            v_inf_arrival = np.linalg.norm(v_arr_helio - v_saturn)
            total_dv += v_inf_arrival

    return total_dv if np.isfinite(total_dv) else PENALTY


def cassini2_verify() -> Dict:
    """Evaluate at the published best solution."""
    x_pub = np.array([
        -779.046753814506, 3.25911446832345, 0.525976214695235, 0.38086496458657,
        167.378952534645, 424.028254165204, 53.2897409769205, 589.766954923325, 2200.0,
        0.769483451363201, 0.513289529822621, 0.0274175362264024, 0.263985256705873, 0.599984695281461,
        1.34877968657176, 1.05, 1.30730278372017, 69.8090142993495,
        -1.5937371121191, -1.95952512232447, -1.55498859283059, -1.5134625299674,
    ])
    f = cassini2_evaluate(x_pub)
    return {
        'published_f': 8.383,
        'our_f': float(f),
        'difference': float(f - 8.383),
    }


def cassini2_run(n_restarts: int = 15, max_iter: int = 1000,
                 pop_size: int = 50, seed: int = 42,
                 verbose: bool = True) -> Dict:
    """Run the Cassini2 MGA-1DSM benchmark optimization."""
    import gc
    from scipy.optimize import minimize

    bounds = CASSINI2_BOUNDS
    strategies = ['best1bin', 'rand1bin', 'currenttobest1bin',
                  'best2bin', 'rand2bin', 'randtobest1bin']
    mutations = [(0.5, 1.5), (0.3, 1.0), (0.7, 1.9),
                 (0.4, 1.2), (0.6, 1.8), (0.5, 1.5)]

    best_x, best_f = None, np.inf

    for i in range(n_restarts):
        gc.collect()
        r = differential_evolution(
            cassini2_evaluate, bounds=bounds,
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
            r = minimize(cassini2_evaluate, best_x, method=method,
                         options={'maxiter': 5000, 'xatol': 1e-12, 'fatol': 1e-12})
            if r.fun < best_f:
                best_f = r.fun
                best_x = r.x.copy()
                if verbose:
                    print(f'  {method}: {r.fun:.4f} ***IMPROVED***', flush=True)
        except Exception:
            pass

    published_best = 8.383
    return {
        'total_dv': float(best_f),
        'published_best': published_best,
        'gap_percent': float((best_f / published_best - 1) * 100),
        'x': best_x.tolist(),
    }
