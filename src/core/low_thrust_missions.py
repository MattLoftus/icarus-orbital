"""Pre-computed electric propulsion missions with visualization.

Wraps the Sims-Flanagan low-thrust optimizer and converts results to
the designed_missions format (events + trajectory_positions + stats).
"""

from typing import Dict
from datetime import datetime, timedelta

import numpy as np
from .low_thrust import optimize_low_thrust, Spacecraft, SimsFlanagan
from .propagate import propagate_kepler
from .constants import MU_SUN


_MJD2000_BASE = datetime(2000, 1, 1)


def _fmt_date(mjd2000: float) -> str:
    return (_MJD2000_BASE + timedelta(days=float(mjd2000))).strftime('%Y-%m-%d')


def _utc_to_mjd2000(utc: str) -> float:
    # Simple UTC string → MJD2000 (ignores sub-second precision, TDB-UTC offset)
    dt = datetime.fromisoformat(utc.replace('Z', '+00:00').split('.')[0]) if 'T' in utc else datetime.fromisoformat(utc)
    return (dt.replace(tzinfo=None) - _MJD2000_BASE).total_seconds() / 86400.0


def _high_res_trajectory(sf: SimsFlanagan, result: Dict, points_per_segment: int = 30):
    """Re-propagate the trajectory with many points per segment for smooth visualization.

    Takes the optimized thrust profile and runs a high-resolution propagation,
    applying impulses at segment midpoints exactly as the Sims-Flanagan does.
    """
    sc = sf.sc
    dt = sf.dt
    n_seg = sf.n_seg

    # Initial state
    r = sf.r_dep.copy()
    v_dep_x = result['x'] if 'x' in result else None
    # Retrieve departure velocity from optimization result via thrust_profile + initial masses
    # The 'trajectory_positions' from low_thrust has the initial position, but velocity is not stored
    # We need to reconstruct v_dep. From the result we have dv_departure_vinf + body state.
    # Safer: use v1_lambert as initial approximation (this is what the solution used)
    # Actually, the thrust_profile dv's will reconstruct the path correctly if we start with v_dep
    # Best approach: re-run to get the actual optimized v_dep
    # The optimize_low_thrust result has trajectory_positions but not v_dep directly — extract by:
    # v_dep = v_dep_body + v_inf_dep_vector
    # But we don't have v_inf_dep_vector, only its magnitude.
    # Simpler: just use the thrust profile and initial r_dep; estimate v_dep from first two positions
    positions = result['trajectory_positions']
    if len(positions) < 2:
        return positions
    # Estimate v_dep from finite difference (first segment, coast dt/2)
    r0 = np.array(positions[0])
    r1 = np.array(positions[1])
    # The first position is r_dep, second is after coast(dt/2) + impulse(seg0) + coast(dt/2)
    # So propagation is complex. Just use the stored positions with interpolation between them.

    # Simpler approach: Lagrange/quadratic interpolation between stored points
    # For a Kepler trajectory, linear interpolation is wrong but gives smooth curves
    # Best alternative: directly re-propagate using the SimsFlanagan infrastructure

    # Re-propagate with high resolution using throttles from optimized result
    throttles = np.array([t['throttle'] for t in result['thrust_profile']])

    # Use the optimized v_dep (now exported from low_thrust)
    v_dep = np.array(result['v_dep_vec'])

    r = sf.r_dep.copy()
    v = v_dep.copy()
    m = sc.m0

    hires_positions = [r.tolist()]
    dt_sub = (dt / 2) / points_per_segment

    for k in range(n_seg):
        # Coast dt/2 with interpolation
        for _ in range(points_per_segment):
            r, v = propagate_kepler(r, v, dt_sub, MU_SUN)
            hires_positions.append(r.tolist())

        # Apply impulse
        dv_max = sc.max_dv_per_segment(dt, m)
        dv = throttles[k] * dv_max
        v = v + dv

        # Mass update
        throttle_mag = np.linalg.norm(throttles[k])
        dm = sc.thrust * dt * throttle_mag / sc.ve
        m = max(m - dm, sc.m_dry)

        # Coast dt/2 with interpolation
        for _ in range(points_per_segment):
            r, v = propagate_kepler(r, v, dt_sub, MU_SUN)
            hires_positions.append(r.tolist())

    return hires_positions


def propagate_low_thrust_mission(dep_body: str, arr_body: str,
                                  dep_date: str, arr_date: str,
                                  thrust_n: float, isp: float,
                                  m0: float, m_dry: float,
                                  n_segments: int = 20,
                                  max_iter: int = 300) -> Dict:
    """Optimize and propagate a low-thrust mission for visualization.

    Returns designed_missions-format dict with events, trajectory_positions, stats.
    """
    # Build Spacecraft and SimsFlanagan so we can re-propagate at high resolution
    sc = Spacecraft(m0=m0, m_dry=m_dry, thrust_n=thrust_n, isp=isp)
    sf = SimsFlanagan(dep_body, arr_body, dep_date, arr_date, sc, n_segments)
    result = sf.optimize(max_iter=max_iter)

    # High-resolution trajectory for smooth visualization
    high_res = _high_res_trajectory(sf, result, points_per_segment=30)
    result['trajectory_positions'] = high_res

    # Events
    dep_label = dep_body.title()
    arr_label = arr_body.title()
    dep_mjd = _utc_to_mjd2000(result['departure_utc'])
    arr_mjd = _utc_to_mjd2000(result['arrival_utc'])

    # Propulsion-dominated → treat as "low-thrust spiral"; no intermediate flybys
    events = [
        {
            'body': dep_label,
            'date': _fmt_date(dep_mjd),
            'type': 'launch',
            'distance_km': 0,
            'dv_gained_km_s': round(float(result['dv_departure_vinf']), 2),
            'heliocentric_position_km': result['trajectory_positions'][0] if result['trajectory_positions'] else [0, 0, 0],
        },
        {
            'body': arr_label,
            'date': _fmt_date(arr_mjd),
            'type': 'arrival',
            'distance_km': 0,
            'dv_gained_km_s': round(float(result['dv_arrival_vinf']), 2),
            'heliocentric_position_km': result['trajectory_positions'][-1] if result['trajectory_positions'] else [0, 0, 0],
        },
    ]

    propulsion = result['propulsion']
    return {
        'events': events,
        'trajectory_positions': result['trajectory_positions'],
        'sequence': [dep_label, arr_label],
        'thrust_profile': result['thrust_profile'],  # optional, for future thrust arrow viz
        'stats': {
            'propulsion_type': 'electric',
            'total_dv_km_s': round(float(result['dv_total']), 3),
            'departure_vinf_km_s': round(float(result['dv_departure_vinf']), 3),
            'arrival_vinf_km_s': round(float(result['dv_arrival_vinf']), 3),
            'tof_days': round(float(result['tof_days']), 1),
            'tof_years': round(float(result['tof_days']) / 365.25, 2),
            'thrust_n': propulsion['thrust_n'],
            'isp_s': propulsion['isp_s'],
            'initial_mass_kg': propulsion['m0_kg'],
            'dry_mass_kg': propulsion['m_dry_kg'],
            'final_mass_kg': round(float(propulsion['m_final_kg']), 1),
            'propellant_mass_kg': round(float(propulsion['propellant_kg']), 1),
            'propellant_fraction': round(float(propulsion['propellant_kg']) / propulsion['m0_kg'] * 100, 1),
            'n_segments': result['n_segments'],
        },
    }


# Pre-computed / configured low-thrust missions
LOW_THRUST_MISSIONS: Dict[str, Dict] = {
    'lt-earth-mars': {
        'name': 'Low-Thrust Earth → Mars',
        'description': 'Electric propulsion transfer from Earth to Mars departing December 2030. '
                       'Uses just 223 kg of xenon propellant (15% of 1500 kg launch mass) — a chemical '
                       'mission would need ~70% propellant for the same Δv. 400-day spiral.',
        'dep_body': 'earth',
        'arr_body': 'mars',
        'dep_date': '2030-12-09',
        'arr_date': '2032-01-13',
        'thrust_n': 0.2,
        'isp': 3000.0,
        'm0': 1500.0,
        'm_dry': 800.0,
        'n_segments': 20,
    },
    'lt-earth-vesta': {
        'name': 'Low-Thrust Earth → Vesta (Dawn-like)',
        'description': 'Ion propulsion rendezvous with asteroid Vesta, modeled after NASA\'s Dawn mission. '
                       '92 mN thrust at 3000s Isp (NSTAR-class thruster). 1300-day transfer from Earth, '
                       '350 kg xenon propellant. Near-zero arrival v_inf (0.55 km/s) — spacecraft '
                       'rendezvous with Vesta for orbital capture.',
        'dep_body': 'earth',
        'arr_body': 'vesta',
        'dep_date': '2029-06-01',
        'arr_date': '2032-12-22',
        'thrust_n': 0.092,
        'isp': 3000.0,
        'm0': 1300.0,
        'm_dry': 748.0,
        'n_segments': 25,
    },
}


def get_low_thrust_mission(mission_id: str) -> Dict:
    """Get a pre-configured low-thrust mission, propagated on demand.

    Note: low-thrust missions run the optimizer on demand (~10-30s per mission)
    rather than storing x* because the decision variables are high-dimensional
    (60+ throttle components) and the optimization is fast enough.
    """
    if mission_id not in LOW_THRUST_MISSIONS:
        return None

    spec = LOW_THRUST_MISSIONS[mission_id]
    result = propagate_low_thrust_mission(
        spec['dep_body'], spec['arr_body'],
        spec['dep_date'], spec['arr_date'],
        spec['thrust_n'], spec['isp'],
        spec['m0'], spec['m_dry'],
        n_segments=spec.get('n_segments', 20),
    )
    result['name'] = spec['name']
    result['description'] = spec['description']
    return result
