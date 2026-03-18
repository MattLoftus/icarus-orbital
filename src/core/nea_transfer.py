"""Compute transfers to Near-Earth Asteroids using orbital elements.

Uses Keplerian propagation from SBDB orbital elements (no SPICE needed
for the asteroid). Earth positions still come from SPICE for accuracy.
"""

import numpy as np
from typing import Dict, Optional, List
from .kepler import propagate_from_elements, propagate_state_from_elements, utc_to_jd
from .lambert import solve_lambert
from .ephemeris import get_body_state, utc_to_et, et_to_utc
from .propagate import generate_trajectory_points
from .constants import MU_SUN


def compute_nea_transfer(elements: Dict, departure_date: str,
                         arrival_date: str) -> Dict:
    """Compute a Lambert transfer from Earth to a NEA.

    Args:
        elements: Dict with keys a, e, i, om, w, ma and epoch_jd (or tp)
                  from fetch_asteroid_elements()
        departure_date: UTC date string
        arrival_date: UTC date string

    Returns:
        Dict with transfer parameters (same format as /api/transfer)
    """
    # Parse elements
    a = elements['a']   # AU
    e = elements['e']
    i = elements.get('i', 0)    # deg
    om = elements.get('om', 0)  # deg
    w = elements.get('w', 0)    # deg
    ma = elements.get('ma', 0)  # deg at epoch

    # Get epoch — try epoch_jd first, fall back to computing from tp
    if 'epoch_jd' in elements and elements['epoch_jd']:
        epoch_jd = elements['epoch_jd']
    else:
        epoch_jd = 2460000.5  # fallback

    # Earth state at departure (from SPICE)
    et_dep = utc_to_et(departure_date)
    earth_state = get_body_state('earth', et_dep)
    earth_pos = earth_state[:3]
    earth_vel = earth_state[3:]

    # NEA state at arrival (from orbital elements)
    arr_jd = utc_to_jd(arrival_date)
    nea_state = propagate_state_from_elements(a, e, i, om, w, ma, epoch_jd, arr_jd)
    nea_pos = nea_state[:3]
    nea_vel = nea_state[3:]

    # Time of flight
    dep_jd = utc_to_jd(departure_date)
    tof_days = arr_jd - dep_jd
    if tof_days <= 0:
        raise ValueError("Arrival must be after departure")
    tof_sec = tof_days * 86400

    # Solve Lambert
    v1, v2 = solve_lambert(earth_pos, nea_pos, tof_sec, MU_SUN)

    dv_dep = float(np.linalg.norm(v1 - earth_vel))
    dv_arr = float(np.linalg.norm(v2 - nea_vel))

    # Generate trajectory points
    positions = generate_trajectory_points(earth_pos, v1, tof_sec, n_points=100)

    return {
        'departure_body': 'earth',
        'arrival_body': elements.get('des', elements.get('name', 'NEA')),
        'departure_utc': departure_date,
        'arrival_utc': arrival_date,
        'tof_days': tof_days,
        'dv_departure': dv_dep,
        'dv_arrival': dv_arr,
        'dv_total': dv_dep + dv_arr,
        'c3_launch': dv_dep**2,
        'v_inf_arrival': dv_arr,
        'v1_transfer': v1.tolist(),
        'v2_transfer': v2.tolist(),
        'trajectory_positions': positions,
        'nea_position': nea_pos.tolist(),
    }


def generate_nea_porkchop(elements: Dict,
                          dep_start: str, dep_end: str,
                          arr_start: str, arr_end: str,
                          dep_steps: int = 60, arr_steps: int = 60
                          ) -> Dict:
    """Generate a porkchop plot for Earth-to-NEA transfer.

    Args:
        elements: Asteroid orbital elements from SBDB
        dep_start, dep_end: Departure window (UTC strings)
        arr_start, arr_end: Arrival window (UTC strings)
        dep_steps, arr_steps: Grid resolution

    Returns:
        Dict with porkchop data (same format as /api/porkchop)
    """
    a = elements['a']
    e = elements['e']
    i_deg = elements.get('i', 0)
    om = elements.get('om', 0)
    w = elements.get('w', 0)
    ma = elements.get('ma', 0)
    epoch_jd = elements.get('epoch_jd', 2460000.5)

    dep_jd_start = utc_to_jd(dep_start)
    dep_jd_end = utc_to_jd(dep_end)
    arr_jd_start = utc_to_jd(arr_start)
    arr_jd_end = utc_to_jd(arr_end)

    dep_jds = np.linspace(dep_jd_start, dep_jd_end, dep_steps)
    arr_jds = np.linspace(arr_jd_start, arr_jd_end, arr_steps)

    # Pre-compute Earth states at each departure date
    dep_ets = [utc_to_et(_jd_to_utc_approx(jd)) for jd in dep_jds]
    earth_states = [get_body_state('earth', et) for et in dep_ets]

    # Pre-compute NEA states at each arrival date
    nea_states = [propagate_state_from_elements(a, e, i_deg, om, w, ma, epoch_jd, jd)
                  for jd in arr_jds]

    dv_total = np.full((dep_steps, arr_steps), np.nan)
    c3_launch = np.full((dep_steps, arr_steps), np.nan)
    v_inf_arr = np.full((dep_steps, arr_steps), np.nan)
    tof_days = np.full((dep_steps, arr_steps), np.nan)

    for di in range(dep_steps):
        r1 = earth_states[di][:3]
        v1_earth = earth_states[di][3:]

        for ai in range(arr_steps):
            tof_d = arr_jds[ai] - dep_jds[di]
            if tof_d <= 10:  # minimum 10 days
                continue

            tof_sec = tof_d * 86400
            r2 = nea_states[ai][:3]
            v2_nea = nea_states[ai][3:]

            try:
                v1_t, v2_t = solve_lambert(r1, r2, tof_sec, MU_SUN)
                dv_d = float(np.linalg.norm(v1_t - v1_earth))
                dv_a = float(np.linalg.norm(v2_t - v2_nea))

                dv_total[di, ai] = dv_d + dv_a
                c3_launch[di, ai] = dv_d**2
                v_inf_arr[di, ai] = dv_a
                tof_days[di, ai] = tof_d
            except (ValueError, RuntimeError):
                continue

        if (di + 1) % 20 == 0:
            print(f"  NEA porkchop: {di+1}/{dep_steps} departure dates computed")

    # Find optimal
    valid = np.isfinite(dv_total)
    optimal = None
    if np.any(valid):
        idx = np.unravel_index(np.nanargmin(dv_total), dv_total.shape)
        oi, oj = idx
        optimal = {
            'dep_utc': _jd_to_utc_approx(dep_jds[oi]),
            'arr_utc': _jd_to_utc_approx(arr_jds[oj]),
            'dv_total': float(dv_total[oi, oj]),
            'c3_launch': float(c3_launch[oi, oj]),
            'tof_days': float(tof_days[oi, oj]),
        }

    # Convert to serializable format
    def clean_array(arr):
        result = arr.tolist()
        return [[None if (isinstance(v, float) and np.isnan(v)) else v for v in row] for row in result]

    dep_utcs = [_jd_to_utc_approx(jd) for jd in dep_jds]
    arr_utcs = [_jd_to_utc_approx(jd) for jd in arr_jds]

    return {
        'departure_body': 'earth',
        'arrival_body': elements.get('des', 'NEA'),
        'dep_dates': dep_utcs,
        'arr_dates': arr_utcs,
        'dv_total': clean_array(dv_total),
        'c3_launch': clean_array(c3_launch),
        'v_inf_arr': clean_array(v_inf_arr),
        'tof_days': clean_array(tof_days),
        'optimal': optimal,
        'resolution': dep_steps,
    }


def _jd_to_utc_approx(jd: float) -> str:
    """Convert Julian Date to approximate UTC string (good to ~1 day)."""
    from datetime import datetime, timedelta
    # J2000 = JD 2451545.0 = 2000-01-01T12:00:00
    j2000 = datetime(2000, 1, 1, 12, 0, 0)
    dt = j2000 + timedelta(days=jd - 2451545.0)
    return dt.strftime('%Y-%m-%dT%H:%M:%S')
