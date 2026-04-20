"""Low-thrust (ion) sample return — ion version of sample_return.py.

Two ion legs (Earth → asteroid → Earth) with a stay at the asteroid.
Compare total propellant mass vs chemical version for the same target.
"""

import numpy as np
from typing import Dict
from datetime import datetime, timedelta

from src.core.jpl_lp import jpl_lp_state, GTOP_MU_SUN
from src.core.low_thrust import Spacecraft, SimsFlanagan
from src.core.low_thrust_missions import _high_res_trajectory
from src.core.propagate import propagate_kepler
from src.core.kepler import propagate_state_from_elements
from src.core.lambert import solve_lambert
from src.core.sample_return import _asteroid_state


_BASE = datetime(2000, 1, 1)


def _build_lt_sample_return_leg(dep_state_fn, arr_state_fn,
                                  dep_date: str, arr_date: str,
                                  thrust_n: float, isp: float,
                                  m0: float, m_dry: float,
                                  n_segments: int = 25) -> Dict:
    """Run Sims-Flanagan for one leg with custom state functions.

    dep_state_fn, arr_state_fn: callables(utc_date_str) → 6-vector state
    """
    from src.core.ephemeris import utc_to_et

    et_dep = utc_to_et(dep_date)
    et_arr = utc_to_et(arr_date)
    dep_state = dep_state_fn(dep_date)
    arr_state = arr_state_fn(arr_date)

    sc = Spacecraft(m0=m0, m_dry=m_dry, thrust_n=thrust_n, isp=isp)
    sf = SimsFlanagan.__new__(SimsFlanagan)
    sf.dep_body = 'dep'
    sf.arr_body = 'arr'
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

    result = sf.optimize(max_iter=300)
    hires = _high_res_trajectory(sf, result, points_per_segment=20)
    return {
        'positions': hires,
        'result': result,
        'sf': sf,
    }


def propagate_lt_sample_return(asteroid_elements: Dict,
                                dep_date: str,
                                outbound_days: float,
                                stay_days: float,
                                return_days: float,
                                thrust_n: float = 0.2,
                                isp: float = 3000.0,
                                m0: float = 1500.0,
                                m_dry_end_outbound: float = 1200.0,
                                m_dry_end_return: float = 950.0,
                                n_segments: int = 20) -> Dict:
    """Build a full ion sample return mission."""
    base = _BASE
    t0 = datetime.fromisoformat(dep_date)
    t_arr_ast = t0 + timedelta(days=outbound_days)
    t_dep_ast = t_arr_ast + timedelta(days=stay_days)
    t_arr_earth = t_dep_ast + timedelta(days=return_days)

    def earth_at(date_str):
        from src.core.ephemeris import utc_to_et, get_body_state
        return get_body_state('earth', utc_to_et(date_str))

    def ast_at(date_str):
        dt = datetime.fromisoformat(date_str)
        mjd = (dt - _BASE).total_seconds() / 86400.0
        return _asteroid_state(asteroid_elements, mjd)

    # Outbound leg
    out = _build_lt_sample_return_leg(
        earth_at, ast_at,
        t0.strftime('%Y-%m-%d'),
        t_arr_ast.strftime('%Y-%m-%d'),
        thrust_n, isp, m0, m_dry_end_outbound,
        n_segments=n_segments,
    )
    positions = list(out['positions'])

    # Stay at asteroid (follow asteroid position)
    n_stay = max(10, int(stay_days / 10))
    for p in range(n_stay):
        frac = p / max(n_stay - 1, 1)
        day_offset = frac * stay_days
        current_date = t_arr_ast + timedelta(days=day_offset)
        state = ast_at(current_date.strftime('%Y-%m-%d'))
        positions.append(state[:3].tolist())

    # Return leg
    ret = _build_lt_sample_return_leg(
        ast_at, earth_at,
        t_dep_ast.strftime('%Y-%m-%d'),
        t_arr_earth.strftime('%Y-%m-%d'),
        thrust_n, isp, m_dry_end_outbound, m_dry_end_return,
        n_segments=n_segments,
    )
    positions.extend(ret['positions'])

    # Stats
    total_propellant = (out['result']['propulsion']['propellant_kg'] +
                        ret['result']['propulsion']['propellant_kg'])
    total_ion_dv = out['result']['dv_total'] + ret['result']['dv_total']
    final_mass = ret['result']['propulsion']['m_final_kg']

    # Events
    ast_name = asteroid_elements.get('name', '').split('(')[0].strip() or asteroid_elements.get('des', 'Asteroid')

    def fmt(d): return d.strftime('%Y-%m-%d')

    events = [
        {'body': 'Earth', 'date': fmt(t0), 'type': 'launch',
         'distance_km': 0,
         'dv_gained_km_s': round(float(out['result']['dv_departure_vinf']), 2),
         'heliocentric_position_km': out['positions'][0] if out['positions'] else [0, 0, 0]},
        {'body': ast_name, 'date': fmt(t_arr_ast), 'type': 'arrival',
         'distance_km': 0,
         'dv_gained_km_s': round(float(out['result']['dv_arrival_vinf']), 2),
         'heliocentric_position_km': ast_at(t_arr_ast.strftime('%Y-%m-%d'))[:3].tolist()},
        {'body': ast_name, 'date': fmt(t_dep_ast), 'type': 'flyby',
         'distance_km': 0,
         'dv_gained_km_s': round(float(ret['result']['dv_departure_vinf']), 2),
         'heliocentric_position_km': ast_at(t_dep_ast.strftime('%Y-%m-%d'))[:3].tolist()},
        {'body': 'Earth', 'date': fmt(t_arr_earth), 'type': 'arrival',
         'distance_km': 0,
         'dv_gained_km_s': round(float(ret['result']['dv_arrival_vinf']), 2),
         'heliocentric_position_km': earth_at(t_arr_earth.strftime('%Y-%m-%d'))[:3].tolist()},
    ]

    return {
        'events': events,
        'trajectory_positions': positions,
        'sequence': ['Earth', ast_name, ast_name, 'Earth'],
        'stats': {
            'propulsion_type': 'electric',
            'total_propellant_kg': round(total_propellant, 1),
            'propellant_fraction': round(total_propellant / m0 * 100, 1),
            'total_ion_dv_km_s': round(total_ion_dv, 3),
            'outbound_dv_km_s': round(float(out['result']['dv_total']), 3),
            'return_dv_km_s': round(float(ret['result']['dv_total']), 3),
            'initial_mass_kg': m0,
            'final_mass_kg': round(float(final_mass), 1),
            'outbound_days': outbound_days,
            'stay_days': stay_days,
            'return_days': return_days,
            'total_duration_years': round((outbound_days + stay_days + return_days) / 365.25, 2),
            'thrust_n': thrust_n,
            'isp_s': isp,
        },
    }
