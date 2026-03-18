"""ESA GTOP benchmark problem implementations.

Implements the Cassini1 benchmark for comparison against published optimal solutions.

The GTOP Cassini1 objective includes:
  - Launch v-infinity (departure delta-v)
  - Powered flyby delta-v at each swing-by (periapsis impulse)
  - Saturn orbit insertion delta-v (into orbit with rp=108,950 km, e=0.98)

Reference: https://www.esa.int/gsp/ACT/projects/gtop/cassini1/
Published best: 4.9307 km/s
"""

import numpy as np
from typing import Dict
from .mga import MGATrajectory
from .constants import MU_SATURN


def saturn_orbit_insertion_dv(v_inf: float) -> float:
    """Compute delta-v for Saturn orbit insertion.

    Target orbit: rp = 108,950 km, e = 0.98
    This matches the GTOP Cassini1 problem definition.

    Args:
        v_inf: Arrival v-infinity at Saturn (km/s)

    Returns:
        Orbit insertion delta-v (km/s)
    """
    rp_target = 108950.0  # km
    e_target = 0.98

    # Velocity at periapsis of the arrival hyperbola
    v_per_hyp = np.sqrt(v_inf**2 + 2 * MU_SATURN / rp_target)

    # Velocity at periapsis of the target orbit
    a_target = rp_target / (1 - e_target)
    v_per_orb = np.sqrt(MU_SATURN * (2 / rp_target - 1 / a_target))

    return abs(v_per_hyp - v_per_orb)


def cassini1(max_iter: int = 500, pop_size: int = 30, seed: int = 42,
             n_restarts: int = 6) -> Dict:
    """Run the GTOP Cassini1 benchmark problem.

    Sequence: Earth → Venus → Venus → Earth → Jupiter → Saturn
    Bounds from GTOP database:
    - Departure: MJD2000 [-1000, 0] (roughly 1997-04 to 2000-01)
    - Leg TOFs: [30,400], [100,470], [30,400], [400,2000], [1000,6000] days

    Returns:
        Dict with optimization result and benchmark comparison.
    """
    prob = MGATrajectory(
        sequence=['earth', 'venus', 'venus', 'earth', 'jupiter', 'saturn'],
        dep_window=('1997-04-01', '2000-01-01'),
        tof_bounds=[
            (30, 400),
            (100, 470),
            (30, 400),
            (400, 2000),
            (1000, 6000),
        ],
        v_inf_max=5.0,
        n_restarts=n_restarts,
    )

    result = prob.optimize(max_iter=max_iter, pop_size=pop_size, seed=seed)

    # Compute Saturn orbit insertion delta-v (not included in our MGA model)
    v_inf_saturn = result.get('arrival_v_inf', 0)
    dv_insertion = saturn_orbit_insertion_dv(v_inf_saturn) if v_inf_saturn > 0 else 0

    # The GTOP total includes insertion; our MGA total does not
    # Our MGA total counts departure v-inf + flyby dvs + arrival v-inf
    # GTOP counts departure v-inf + flyby dvs + insertion dv (NOT raw v-inf)
    # So the fair comparison is: our_total - arrival_v_inf + insertion_dv
    gtop_equivalent_dv = result['total_dv'] - v_inf_saturn + dv_insertion

    published_best = 4.9307

    result['benchmark'] = {
        'name': 'GTOP Cassini1',
        'published_best_dv': published_best,
        'our_mga_dv': result['total_dv'],
        'our_gtop_equivalent_dv': gtop_equivalent_dv,
        'saturn_insertion_dv': dv_insertion,
        'arrival_v_inf': v_inf_saturn,
        'ratio': gtop_equivalent_dv / published_best,
        'gap_percent': (gtop_equivalent_dv / published_best - 1) * 100,
    }

    return result


def cassini1_quick(seed: int = 42) -> Dict:
    """Quick version — single restart, fewer iterations."""
    return cassini1(max_iter=200, pop_size=20, seed=seed, n_restarts=1)
