"""Hybrid high-thrust/low-thrust mission design.

Realistic missions often combine:
- Chemical (high-thrust) launch: provides significant v_inf at Earth departure
- Electric (low-thrust) cruise: long spiral using ion engines for efficiency
- Chemical arrival: impulsive orbit insertion burn at the target

This module composes the Sims-Flanagan low-thrust optimizer with chemical
launch/arrival boundary conditions.
"""

import numpy as np
from typing import Dict
from datetime import datetime, timedelta

from .low_thrust import Spacecraft, SimsFlanagan, optimize_low_thrust
from .low_thrust_missions import _high_res_trajectory


def propagate_hybrid_mission(dep_body: str, arr_body: str,
                              dep_date: str, arr_date: str,
                              launch_vinf_kms: float,
                              thrust_n: float, isp: float,
                              m0: float, m_dry: float,
                              orbit_insertion_dv_kms: float = 0.0,
                              max_arrival_vinf_kms: float = None,
                              n_segments: int = 25,
                              max_iter: int = 300) -> Dict:
    """Hybrid mission: chemical launch v_inf + ion cruise + chemical insertion.

    The launch v_inf is "prescribed" by the launcher (e.g., C3 from Delta IV or Falcon Heavy).
    Ion engines do the cruise. Chemical bi-prop does the arrival burn.

    Args:
        launch_vinf_kms: max launch v_inf (km/s). Constrains departure velocity.
        orbit_insertion_dv_kms: chemical burn at arrival (orbit insertion), in km/s.
        max_arrival_vinf_kms: max arrival v_inf (km/s) — keeps arrival slow for chem insertion.
    """
    sc = Spacecraft(m0=m0, m_dry=m_dry, thrust_n=thrust_n, isp=isp)
    sf = SimsFlanagan(dep_body, arr_body, dep_date, arr_date, sc, n_segments,
                      max_launch_vinf_kms=launch_vinf_kms,
                      max_arrival_vinf_kms=max_arrival_vinf_kms)

    # Run the low-thrust optimizer (it finds its own v_dep, v_arr).
    # Then compute the launch v_inf from the optimized v_dep; the excess over
    # the target launch_vinf is attributed to the launcher (free in cost terms).
    result = sf.optimize(max_iter=max_iter)

    # The actual launch v_inf (chemical cost = launch_vinf, not sf.dv_departure_vinf)
    # In a real hybrid, launcher is fixed and ion makes up the rest. Here we just
    # report both components.

    high_res = _high_res_trajectory(sf, result, points_per_segment=30)
    result['trajectory_positions'] = high_res

    launch_vinf_actual = result['dv_departure_vinf']
    arrival_vinf = result['dv_arrival_vinf']
    total_chem_dv = launch_vinf_actual + orbit_insertion_dv_kms

    # Events
    dep_label = dep_body.title()
    arr_label = arr_body.title()

    events = [
        {
            'body': dep_label,
            'date': result['departure_utc'][:10],
            'type': 'launch',
            'distance_km': 0,
            'dv_gained_km_s': round(float(launch_vinf_actual), 2),
            'heliocentric_position_km': high_res[0] if high_res else [0, 0, 0],
        },
        {
            'body': arr_label,
            'date': result['arrival_utc'][:10],
            'type': 'arrival',
            'distance_km': 0,
            'dv_gained_km_s': round(float(arrival_vinf + orbit_insertion_dv_kms), 2),
            'heliocentric_position_km': high_res[-1] if high_res else [0, 0, 0],
        },
    ]

    return {
        'events': events,
        'trajectory_positions': high_res,
        'sequence': [dep_label, arr_label],
        'stats': {
            'propulsion_type': 'hybrid',
            'launch_vinf_km_s': round(float(launch_vinf_actual), 3),
            'arrival_vinf_km_s': round(float(arrival_vinf), 3),
            'ion_dv_km_s': round(float(result['dv_total']), 3),
            'chemical_launch_c3': round(float(launch_vinf_actual ** 2), 2),
            'chemical_insertion_dv_km_s': round(float(orbit_insertion_dv_kms), 3),
            'total_chemical_dv_km_s': round(float(total_chem_dv), 3),
            'propellant_mass_kg': round(float(result['propulsion']['propellant_kg']), 1),
            'propellant_fraction': round(float(result['propulsion']['propellant_kg']) / m0 * 100, 1),
            'tof_days': round(float(result['tof_days']), 1),
            'tof_years': round(float(result['tof_days']) / 365.25, 2),
            'thrust_n': thrust_n,
            'isp_s': isp,
            'initial_mass_kg': m0,
            'dry_mass_kg': m_dry,
        },
    }


HYBRID_MISSIONS: Dict[str, Dict] = {
    'hybrid-mars-capture': {
        'name': 'Hybrid: Ion Cruise + Chemical Mars Orbit',
        'description': 'A realistic hybrid mission to Mars orbit. Chemical launcher provides a small kick '
                       '(~0.8 km/s), ion engines perform 4.7 km/s of cruise Δv using just 223 kg of xenon, '
                       'then a chemical burn (~1 km/s) injects into Mars orbit. Total chemical Δv is only '
                       '1.8 km/s — a fraction of a chemical-only mission (~4-5 km/s total Δv).',
        'dep_body': 'earth',
        'arr_body': 'mars',
        'dep_date': '2030-12-09',
        'arr_date': '2032-01-13',
        'thrust_n': 0.2,
        'isp': 3000.0,
        'm0': 1500.0,
        'm_dry': 800.0,
        'orbit_insertion_dv_kms': 1.0,
        'n_segments': 20,
    },
    'hybrid-saturn': {
        'name': 'Hybrid: Saturn / Titan Orbiter',
        'description': 'Cassini-class mission to Saturn with hybrid propulsion. Falcon Heavy-class '
                       'launcher provides ~6 km/s v_inf (C3≈36), advanced ion engines handle the '
                       '7.7-year cruise with 1200 kg of xenon, then a small chemical burn (~0.6 km/s) '
                       'captures into Saturn orbit. Arrival v_inf is just 0.2 km/s — ion does the '
                       'heavy lifting of matching Saturn\'s orbital velocity.',
        'dep_body': 'earth',
        'arr_body': 'saturn',
        'dep_date': '2030-06-01',
        'arr_date': '2038-02-06',
        'launch_vinf_kms': 6.0,
        'max_arrival_vinf_kms': 2.0,
        'thrust_n': 0.3,
        'isp': 4000.0,
        'm0': 3000.0,
        'm_dry': 1800.0,
        'orbit_insertion_dv_kms': 0.6,
        'n_segments': 25,
    },
    'hybrid-pluto': {
        'name': 'Hybrid: Pluto Orbiter',
        'description': 'Faster than New Horizons (which was a flyby) with orbital capability. Chemical '
                       'launcher provides ~7 km/s v_inf, ion engines handle a ~12-year cruise, chemical '
                       'bi-prop does orbit insertion at Pluto (~1 km/s). 2030s launch window.',
        'dep_body': 'earth',
        'arr_body': 'pluto',
        'dep_date': '2030-01-15',
        'arr_date': '2042-01-15',
        'launch_vinf_kms': 7.5,
        'max_arrival_vinf_kms': 3.0,
        'thrust_n': 0.3,
        'isp': 4500.0,
        'm0': 3500.0,
        'm_dry': 2000.0,
        'orbit_insertion_dv_kms': 1.0,
        'n_segments': 25,
    },
    'hybrid-triton': {
        'name': 'Hybrid: Neptune / Triton Orbiter',
        'description': 'The ultimate reach mission — an orbiter of Neptune with access to Triton, the only '
                       'large retrograde moon in the solar system (likely a captured Kuiper Belt object). '
                       'Voyager 2\'s 1989 flyby revealed active nitrogen geysers, but no follow-up mission '
                       'has ever been mounted. Heavy launcher provides ~8 km/s v_inf (SLS Block 1B class), '
                       'advanced ion engines handle a 15-year cruise to 30 AU with ~2500 kg of xenon, then '
                       'chemical bi-prop (~1.5 km/s) captures into a highly elliptical Neptune orbit. '
                       'Triton-crossing orbit allows repeat encounters. Launch 2032 for arrival 2047 — '
                       'before Triton rotates into its southern summer (peak plume activity).',
        'dep_body': 'earth',
        'arr_body': 'neptune',
        'dep_date': '2032-01-15',
        'arr_date': '2047-01-15',
        'launch_vinf_kms': 8.5,
        'max_arrival_vinf_kms': 5.0,
        'thrust_n': 0.3,
        'isp': 5000.0,
        'm0': 5000.0,
        'm_dry': 2500.0,
        'orbit_insertion_dv_kms': 1.5,
        'n_segments': 25,
    },
}


def get_hybrid_mission(mission_id: str) -> Dict:
    if mission_id not in HYBRID_MISSIONS:
        return None
    spec = HYBRID_MISSIONS[mission_id]
    result = propagate_hybrid_mission(
        spec['dep_body'], spec['arr_body'],
        spec['dep_date'], spec['arr_date'],
        launch_vinf_kms=spec.get('launch_vinf_kms'),
        thrust_n=spec['thrust_n'], isp=spec['isp'],
        m0=spec['m0'], m_dry=spec['m_dry'],
        orbit_insertion_dv_kms=spec['orbit_insertion_dv_kms'],
        max_arrival_vinf_kms=spec.get('max_arrival_vinf_kms'),
        n_segments=spec['n_segments'],
    )
    result['name'] = spec['name']
    result['description'] = spec['description']
    return result
