"""Chemical flyby missions to small bodies (comets, asteroids).

Unlike rendezvous missions, flybys only require intercepting the target's
position at a given time — no velocity matching. This makes retrograde or
high-inclination targets (like Halley) tractable with chemical propulsion.

Key physics: Lambert transfer from Earth to target's position at encounter.
The relative velocity at encounter is the "flyby velocity" — not a cost,
but an important mission parameter (affects imaging cadence, shield design).
"""

import numpy as np
from typing import Dict
from datetime import datetime, timedelta

from src.core.jpl_lp import jpl_lp_state, GTOP_MU_SUN
from src.core.ephemeris import get_body_state, utc_to_et
from src.core.lambert import solve_lambert
from src.core.propagate import propagate_kepler
from src.core.kepler import propagate_state_from_elements, utc_to_jd
from src.core.constants import MU_SUN


_BASE = datetime(2000, 1, 1)


def propagate_flyby_mission(target_name: str,
                             dep_date: str, arr_date: str,
                             target_elements: Dict,
                             include_post_flyby_days: float = 365.0,
                             n_points_leg: int = 300) -> Dict:
    """Chemical flyby mission: Earth → target body at a fixed arrival date.

    Optionally propagate the post-flyby coast to show the spacecraft
    continuing after the encounter.
    """
    et_dep = utc_to_et(dep_date)
    et_arr = utc_to_et(arr_date)
    tof_sec = et_arr - et_dep

    # Earth state at departure
    earth_state = get_body_state('earth', et_dep)
    r_earth = earth_state[:3]
    v_earth = earth_state[3:]

    # Target state at encounter
    target_jd = utc_to_jd(arr_date)
    target_state = propagate_state_from_elements(
        target_elements['a'], target_elements['e'], target_elements['i'],
        target_elements['om'], target_elements['w'], target_elements['ma'],
        target_elements['epoch_jd'], target_jd,
    )
    r_target = target_state[:3]
    v_target = target_state[3:]

    # Lambert transfer
    v1, v2 = solve_lambert(r_earth, r_target, tof_sec, MU_SUN)

    # Departure v_inf (Earth escape cost)
    v_inf_dep = np.linalg.norm(v1 - v_earth)

    # Flyby velocity (relative to target at encounter)
    v_flyby = np.linalg.norm(v2 - v_target)

    # Propagate the trajectory with high resolution
    positions = []
    n = n_points_leg
    dt = tof_sec / n
    r, v = r_earth.copy(), v1.copy()
    for i in range(n + 1):
        positions.append(r.tolist())
        if i < n:
            r, v = propagate_kepler(r, v, dt, MU_SUN)

    # Optional post-flyby coast
    if include_post_flyby_days > 0:
        post_dt = include_post_flyby_days * 86400.0
        n_post = max(50, int(include_post_flyby_days / 3))
        dt_post = post_dt / n_post
        r, v = r_target.copy(), v2.copy()  # start from encounter with v2
        for i in range(n_post):
            r, v = propagate_kepler(r, v, dt_post, MU_SUN)
            positions.append(r.tolist())

    # Events
    events = [
        {
            'body': 'Earth',
            'date': dep_date,
            'type': 'launch',
            'distance_km': 0,
            'dv_gained_km_s': round(float(v_inf_dep), 2),
            'heliocentric_position_km': r_earth.tolist(),
        },
        {
            'body': target_name,
            'date': arr_date,
            'type': 'flyby',
            'distance_km': 0,
            'dv_gained_km_s': round(float(v_flyby), 2),  # flyby relative velocity
            'heliocentric_position_km': r_target.tolist(),
        },
    ]

    if include_post_flyby_days > 0:
        final_date = (datetime.fromisoformat(arr_date) +
                      timedelta(days=include_post_flyby_days)).strftime('%Y-%m-%d')
        events.append({
            'body': 'Deep Space',
            'date': final_date,
            'type': 'arrival',
            'distance_km': 0,
            'dv_gained_km_s': 0.0,
            'heliocentric_position_km': positions[-1] if positions else [0, 0, 0],
        })

    tof_days = (datetime.fromisoformat(arr_date) - datetime.fromisoformat(dep_date)).days

    return {
        'events': events,
        'trajectory_positions': positions,
        'sequence': ['Earth', target_name],
        'stats': {
            'propulsion_type': 'chemical',
            'launch_vinf_km_s': round(float(v_inf_dep), 3),
            'launch_c3_km2_s2': round(float(v_inf_dep ** 2), 1),
            'flyby_velocity_km_s': round(float(v_flyby), 3),
            'tof_days': tof_days,
            'tof_years': round(tof_days / 365.25, 2),
        },
    }


# --- Halley's Comet orbital elements ---
# From JPL SBDB epoch JD 2439875.5 = 1967-12-08 (pre-1986 return)
# Halley has a 76-year period and is retrograde (i = 162°)
# Next perihelion: 2061-07-28

HALLEY_ELEMENTS = {
    'a': 17.929,      # AU
    'e': 0.968,
    'i': 162.19,      # deg, retrograde
    'om': 59.099,     # deg
    'w': 112.241,     # deg (argument of perihelion)
    'ma': 274.38,     # deg (mean anomaly at epoch)
    'epoch_jd': 2439875.5,
}
