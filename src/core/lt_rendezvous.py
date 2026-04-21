"""Low-thrust (ion) rendezvous — one-way ion missions to targets.

Unlike lt_sample_return.py (round-trip), these are one-way missions:
Earth → Target with ion rendezvous at target.

Targets can be planets, dwarf planets, or arbitrary small bodies
(specified via Keplerian orbital elements).
"""

import numpy as np
from typing import Dict, Optional
from datetime import datetime, timedelta

from src.core.jpl_lp import jpl_lp_state, GTOP_MU_SUN
from src.core.low_thrust import Spacecraft, SimsFlanagan
from src.core.low_thrust_missions import _high_res_trajectory
from src.core.lambert import solve_lambert
from src.core.kepler import propagate_state_from_elements


_BASE = datetime(2000, 1, 1)


def _body_state_at(body: str, date: str,
                   custom_elements: Optional[Dict] = None) -> np.ndarray:
    """Get state (km, km/s) for a body at a UTC date. Supports custom Keplerian elements."""
    if custom_elements:
        dt = datetime.fromisoformat(date)
        mjd2000 = (dt - _BASE).total_seconds() / 86400.0
        # Propagate custom elements
        # elements dict: a (AU), e, i (deg), om (deg), w (deg), ma (deg), epoch_jd
        from src.core.kepler import utc_to_jd
        target_jd = utc_to_jd(date)
        return propagate_state_from_elements(
            custom_elements['a'], custom_elements['e'], custom_elements['i'],
            custom_elements['om'], custom_elements['w'], custom_elements['ma'],
            custom_elements['epoch_jd'], target_jd,
        )
    from src.core.ephemeris import get_body_state, utc_to_et
    return get_body_state(body, utc_to_et(date))


def propagate_lt_rendezvous(target_name: str,
                             dep_date: str, arr_date: str,
                             thrust_n: float, isp: float,
                             m0: float, m_dry: float,
                             n_segments: int = 25,
                             target_elements: Optional[Dict] = None,
                             max_iter: int = 300) -> Dict:
    """Ion rendezvous from Earth to target body.

    If target_elements is given, use them; otherwise look up in ephemeris.
    """
    from src.core.ephemeris import utc_to_et

    et_dep = utc_to_et(dep_date)
    et_arr = utc_to_et(arr_date)

    dep_state = _body_state_at('earth', dep_date)
    arr_state = _body_state_at(target_name, arr_date, target_elements)

    sc = Spacecraft(m0=m0, m_dry=m_dry, thrust_n=thrust_n, isp=isp)
    sf = SimsFlanagan.__new__(SimsFlanagan)
    sf.dep_body = 'earth'
    sf.arr_body = target_name
    sf.sc = sc
    sf.n_seg = n_segments
    sf.n_fwd = n_segments // 2
    sf.n_bwd = n_segments - sf.n_fwd
    sf.et_dep = et_dep
    sf.et_arr = et_arr
    sf.tof = et_arr - et_dep
    sf.dt = sf.tof / n_segments
    sf.dep_state = dep_state
    sf.v_dep_body = dep_state[3:]
    sf.r_dep = dep_state[:3]
    sf.arr_state = arr_state
    sf.v_arr_body = arr_state[3:]
    sf.r_arr = arr_state[:3]
    sf.max_launch_vinf = None
    sf.max_arrival_vinf = None
    sf.v1_lambert, sf.v2_lambert = solve_lambert(sf.r_dep, sf.r_arr, sf.tof, GTOP_MU_SUN)

    result = sf.optimize(max_iter=max_iter)
    hires = _high_res_trajectory(sf, result, points_per_segment=20)

    tof_days = (datetime.fromisoformat(arr_date) - datetime.fromisoformat(dep_date)).days

    events = [
        {
            'body': 'Earth',
            'date': dep_date,
            'type': 'launch',
            'distance_km': 0,
            'dv_gained_km_s': round(float(result['dv_departure_vinf']), 2),
            'heliocentric_position_km': hires[0] if hires else [0, 0, 0],
        },
        {
            'body': target_name.title() if target_name.islower() else target_name,
            'date': arr_date,
            'type': 'arrival',
            'distance_km': 0,
            'dv_gained_km_s': round(float(result['dv_arrival_vinf']), 2),
            'heliocentric_position_km': hires[-1] if hires else [0, 0, 0],
        },
    ]

    return {
        'events': events,
        'trajectory_positions': hires,
        'sequence': ['Earth', target_name.title() if target_name.islower() else target_name],
        'stats': {
            'propulsion_type': 'electric',
            'departure_vinf_km_s': round(float(result['dv_departure_vinf']), 3),
            'arrival_vinf_km_s': round(float(result['dv_arrival_vinf']), 3),
            'total_ion_dv_km_s': round(float(result['dv_total']), 3),
            'propellant_mass_kg': round(float(result['propulsion']['propellant_kg']), 1),
            'propellant_fraction': round(float(result['propulsion']['propellant_kg']) / m0 * 100, 1),
            'final_mass_kg': round(float(result['propulsion']['m_final_kg']), 1),
            'initial_mass_kg': m0,
            'tof_days': tof_days,
            'tof_years': round(tof_days / 365.25, 2),
            'thrust_n': thrust_n,
            'isp_s': isp,
        },
    }


# --- Target orbital elements ---
# From JPL SBDB, epoch JD 2461000.5 (= MJD2000 = 9455.5, ≈ 2025-12-02)

APOPHIS_ELEMENTS = {
    'a': 0.9224, 'e': 0.1912, 'i': 3.34,
    'om': 203.90, 'w': 126.67, 'ma': 312.81,
    'epoch_jd': 2461000.5,
}

CHIRON_ELEMENTS = {
    'a': 13.692, 'e': 0.379, 'i': 6.93,
    'om': 209.30, 'w': 339.25, 'ma': 212.84,
    'epoch_jd': 2461000.5,
}
