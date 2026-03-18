"""Porkchop plot generation — grid of Lambert solutions over departure/arrival windows."""

import numpy as np
from typing import Dict, Optional
from .lambert import solve_lambert
from .ephemeris import get_body_state, utc_to_et, et_to_utc
from .constants import MU_SUN


def generate_porkchop(departure_body: str, arrival_body: str,
                      dep_start: str, dep_end: str,
                      arr_start: str, arr_end: str,
                      dep_steps: int = 200, arr_steps: int = 200,
                      prograde: bool = True) -> Dict:
    """Generate porkchop plot data for a transfer between two bodies.

    Args:
        departure_body: Name of departure body (e.g., 'earth')
        arrival_body: Name of arrival body (e.g., 'mars')
        dep_start, dep_end: Departure window (UTC strings)
        arr_start, arr_end: Arrival window (UTC strings)
        dep_steps: Number of departure date grid points
        arr_steps: Number of arrival date grid points
        prograde: If True, compute prograde transfers

    Returns:
        Dict with keys:
            dep_dates: array of departure ETs
            arr_dates: array of arrival ETs
            dep_utc: list of departure UTC strings
            arr_utc: list of arrival UTC strings
            c3_launch: 2D array of launch C3 (km^2/s^2)
            v_inf_arr: 2D array of arrival v-infinity (km/s)
            dv_total: 2D array of total delta-v (km/s)
            tof_days: 2D array of time-of-flight (days)
    """
    et_dep_start = utc_to_et(dep_start)
    et_dep_end = utc_to_et(dep_end)
    et_arr_start = utc_to_et(arr_start)
    et_arr_end = utc_to_et(arr_end)

    dep_ets = np.linspace(et_dep_start, et_dep_end, dep_steps)
    arr_ets = np.linspace(et_arr_start, et_arr_end, arr_steps)

    c3_launch = np.full((dep_steps, arr_steps), np.nan)
    v_inf_arr = np.full((dep_steps, arr_steps), np.nan)
    dv_total = np.full((dep_steps, arr_steps), np.nan)
    tof_days = np.full((dep_steps, arr_steps), np.nan)

    # Pre-fetch departure body states
    dep_states = np.array([get_body_state(departure_body, et) for et in dep_ets])
    arr_states = np.array([get_body_state(arrival_body, et) for et in arr_ets])

    for i in range(dep_steps):
        r1 = dep_states[i, :3]
        v1_body = dep_states[i, 3:]

        for j in range(arr_steps):
            tof_sec = arr_ets[j] - dep_ets[i]
            if tof_sec <= 0:
                continue

            tof_days[i, j] = tof_sec / 86400.0

            r2 = arr_states[j, :3]
            v2_body = arr_states[j, 3:]

            try:
                v1_transfer, v2_transfer = solve_lambert(
                    r1, r2, tof_sec, MU_SUN, prograde=prograde
                )

                # Departure: v-infinity = transfer velocity - body velocity
                v_inf_dep = v1_transfer - v1_body
                v_inf_dep_mag = np.linalg.norm(v_inf_dep)

                # Arrival: v-infinity = transfer velocity - body velocity
                v_inf_arr_vec = v2_transfer - v2_body
                v_inf_arr_mag = np.linalg.norm(v_inf_arr_vec)

                c3_launch[i, j] = v_inf_dep_mag**2
                v_inf_arr[i, j] = v_inf_arr_mag
                dv_total[i, j] = v_inf_dep_mag + v_inf_arr_mag

            except (ValueError, RuntimeError):
                continue

        # Progress reporting for long computations
        if (i + 1) % 50 == 0:
            print(f"  Porkchop: {i+1}/{dep_steps} departure dates computed")

    dep_utc = [et_to_utc(et) for et in dep_ets]
    arr_utc = [et_to_utc(et) for et in arr_ets]

    return {
        'departure_body': departure_body,
        'arrival_body': arrival_body,
        'dep_dates': dep_ets,
        'arr_dates': arr_ets,
        'dep_utc': dep_utc,
        'arr_utc': arr_utc,
        'c3_launch': c3_launch,
        'v_inf_arr': v_inf_arr,
        'dv_total': dv_total,
        'tof_days': tof_days,
    }


def find_optimal_transfer(porkchop_data: Dict) -> Optional[Dict]:
    """Find the minimum total delta-v transfer from porkchop data.

    Returns:
        Dict with departure/arrival dates, delta-v components, TOF, or None if no valid transfers.
    """
    dv = porkchop_data['dv_total']
    valid = np.isfinite(dv)
    if not np.any(valid):
        return None

    idx = np.unravel_index(np.nanargmin(dv), dv.shape)
    i, j = idx

    return {
        'dep_et': porkchop_data['dep_dates'][i],
        'arr_et': porkchop_data['arr_dates'][j],
        'dep_utc': porkchop_data['dep_utc'][i],
        'arr_utc': porkchop_data['arr_utc'][j],
        'dv_total': float(dv[i, j]),
        'c3_launch': float(porkchop_data['c3_launch'][i, j]),
        'v_inf_arrival': float(porkchop_data['v_inf_arr'][i, j]),
        'tof_days': float(porkchop_data['tof_days'][i, j]),
    }
