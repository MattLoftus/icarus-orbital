"""Historical electric propulsion and hybrid missions.

Real-world missions that used ion propulsion, solar sails, or hybrid systems.
Reconstructs trajectories using the actual event timelines and real spacecraft
parameters. Each leg uses the appropriate physics engine:

- Ion cruise legs: Sims-Flanagan low-thrust optimizer (src/core/low_thrust.py)
- Ballistic gravity assists: Lambert solver (src/core/lambert.py)
- Orbit phases: follow the target body's position in time
- Sample return: 2-leg round-trip (outbound + return Lambert)
- Solar sail: continuous thrust RK4 integration (src/core/solar_sail.py)

Each mission is defined by its real event timeline (dates, bodies) and real
spacecraft parameters (thrust, Isp, mass).
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

from src.core.low_thrust import Spacecraft, SimsFlanagan
from src.core.low_thrust_missions import _high_res_trajectory
from src.core.propagate import propagate_kepler
from src.core.ephemeris import get_body_state, utc_to_et
from src.core.kepler import propagate_state_from_elements
from src.core.lambert import solve_lambert
from src.core.constants import MU_SUN


_BASE = datetime(2000, 1, 1)


def _utc_to_mjd2000(utc: str) -> float:
    """YYYY-MM-DD → MJD2000."""
    dt = datetime.strptime(utc, '%Y-%m-%d')
    return (dt - _BASE).total_seconds() / 86400.0


def _get_body_state_for_leg(body: str, date: str, element_overrides: Dict = None):
    """Get body state at a given date.

    For planets and dwarf planets, uses SPICE + Keplerian fallback.
    For asteroids not in our ephemeris, accepts element_overrides dict.
    """
    et = utc_to_et(date)
    if element_overrides and body in element_overrides:
        elem = element_overrides[body]
        from src.core.kepler import utc_to_jd
        jd = utc_to_jd(date)
        return propagate_state_from_elements(
            elem['a'], elem['e'], elem['i'],
            elem['om'], elem['w'], elem['ma'],
            elem['epoch_jd'], jd,
        )
    return get_body_state(body, et)


def _propagate_ion_leg(dep_body: str, arr_body: str,
                       dep_date: str, arr_date: str,
                       thrust_n: float, isp: float,
                       m0: float, m_dry: float,
                       n_segments: int = 20,
                       element_overrides: Dict = None,
                       max_iter: int = 200) -> Dict:
    """Optimize a single ion cruise leg between two bodies/dates.

    Returns high-res trajectory positions + end state + mass used.
    """
    sc = Spacecraft(m0=m0, m_dry=m_dry, thrust_n=thrust_n, isp=isp)

    # If one of the bodies isn't in default ephemeris, we need custom handling
    # For now, treat planet-like and dwarf planets uniformly via get_body_state
    if element_overrides:
        # Patch: we'd need to modify SimsFlanagan to accept custom bodies.
        # For simplicity, compute states manually and build the leg.
        et_dep = utc_to_et(dep_date)
        et_arr = utc_to_et(arr_date)
        dep_state = _get_body_state_for_leg(dep_body, dep_date, element_overrides)
        arr_state = _get_body_state_for_leg(arr_body, arr_date, element_overrides)

        # Monkey-patch SimsFlanagan construction by passing states directly
        sf = SimsFlanagan.__new__(SimsFlanagan)
        sf.dep_body = dep_body
        sf.arr_body = arr_body
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
        sf.v1_lambert, sf.v2_lambert = solve_lambert(
            sf.r_dep, sf.r_arr, sf.tof, MU_SUN)
    else:
        sf = SimsFlanagan(dep_body, arr_body, dep_date, arr_date, sc, n_segments)

    result = sf.optimize(max_iter=max_iter)
    hires = _high_res_trajectory(sf, result, points_per_segment=20)

    return {
        'positions': hires,
        'dep_state': sf.dep_state.tolist(),
        'arr_state': sf.arr_state.tolist(),
        'v_dep_optimized': result.get('v_dep_vec', sf.v1_lambert.tolist()),
        'v_arr_optimized': result.get('v_arr_vec', sf.v2_lambert.tolist()),
        'ion_dv': result['dv_total'],
        'propellant_kg': result['propulsion']['propellant_kg'],
        'final_mass_kg': result['propulsion']['m_final_kg'],
        'tof_days': result['tof_days'],
    }


def _propagate_ballistic_leg(dep_body: str, arr_body: str,
                              dep_date: str, arr_date: str,
                              element_overrides: Dict = None,
                              n_points: int = 100) -> Dict:
    """Propagate a ballistic (Lambert) leg — for gravity assists and coast phases."""
    dep_state = _get_body_state_for_leg(dep_body, dep_date, element_overrides)
    arr_state = _get_body_state_for_leg(arr_body, arr_date, element_overrides)

    dep_mjd = _utc_to_mjd2000(dep_date)
    arr_mjd = _utc_to_mjd2000(arr_date)
    tof_sec = (arr_mjd - dep_mjd) * 86400.0

    v1, v2 = solve_lambert(dep_state[:3], arr_state[:3], tof_sec, MU_SUN)

    # Propagate with many points
    positions = []
    dt = tof_sec / n_points
    r, v = dep_state[:3].copy(), v1.copy()
    for p in range(n_points + 1):
        positions.append(r.tolist())
        if p < n_points:
            r, v = propagate_kepler(r, v, dt, MU_SUN)

    return {
        'positions': positions,
        'dep_state': dep_state.tolist(),
        'arr_state': arr_state.tolist(),
        'v1_lambert': v1.tolist(),
        'v2_lambert': v2.tolist(),
        'tof_days': (arr_mjd - dep_mjd),
    }


def _follow_body(body: str, start_date: str, end_date: str,
                  n_points: int = 50,
                  element_overrides: Dict = None) -> List[List[float]]:
    """Return positions of a body from start_date to end_date (for orbit phases)."""
    start_mjd = _utc_to_mjd2000(start_date)
    end_mjd = _utc_to_mjd2000(end_date)
    positions = []
    for i in range(n_points + 1):
        frac = i / n_points if n_points > 0 else 0
        t_mjd = start_mjd + frac * (end_mjd - start_mjd)
        date_str = (_BASE + timedelta(days=t_mjd)).strftime('%Y-%m-%d')
        state = _get_body_state_for_leg(body, date_str, element_overrides)
        positions.append(state[:3].tolist())
    return positions


# --- Asteroid element overrides for bodies not in our SPICE ephemeris ---
# Elements from JPL Small-Body Database
_ASTEROID_ELEMENTS_EARLY = {
    'itokawa': {
        'a': 1.3241, 'e': 0.2800, 'i': 1.6217,
        'om': 69.0763, 'w': 162.8277, 'ma': 323.5395,
        'epoch_jd': 2460200.5,
    },
    'ryugu': {
        'a': 1.1898, 'e': 0.1903, 'i': 5.8837,
        'om': 251.5900, 'w': 211.4349, 'ma': 100.1015,
        'epoch_jd': 2460200.5,
    },
    'psyche': {
        'a': 2.9238, 'e': 0.1340, 'i': 3.0969,
        'om': 150.0370, 'w': 229.2310, 'ma': 172.3143,
        'epoch_jd': 2460200.5,
    },
}


def build_dawn_mission() -> Dict:
    """Dawn — Earth → Mars gravity assist → Vesta → Ceres (2007-2018).

    Used NSTAR ion thrusters for all interplanetary cruise. ~10 kg of xenon
    for the entire mission. First spacecraft to orbit two extraterrestrial bodies.

    Real event timeline:
      - Launch: 2007-09-27
      - Mars gravity assist: 2009-02-17
      - Vesta orbit insertion: 2011-07-16
      - Depart Vesta: 2012-09-05
      - Ceres orbit insertion: 2015-03-06
      - End of mission: 2018-10-31
    """
    # Dawn parameters: NSTAR thrusters (3 redundant), 92 mN max, 3000s Isp
    # Launch mass 1217 kg, dry mass 747 kg (370 kg xenon fuel)
    # For reconstruction, use slightly relaxed parameters since actual mission
    # had many adjustments and Mars GA was unpowered
    m0 = 1217.0
    m_dry_end_phase1 = 1100.0  # approximate after E→Mars ion use
    m_dry_end_phase2 = 950.0   # after Mars→Vesta
    m_dry_end_phase3 = 800.0   # after Vesta→Ceres

    phases = [
        # Phase 1: E→Mars (ion cruise with Mars flyby target)
        {
            'type': 'ion',
            'dep_body': 'earth',
            'arr_body': 'mars',
            'dep_date': '2007-09-27',
            'arr_date': '2009-02-17',
            'thrust_n': 0.092,
            'isp': 3000.0,
            'm0': m0,
            'm_dry': m_dry_end_phase1,
            'n_segments': 25,
        },
        # Phase 2: Mars→Vesta (ion cruise, longest leg)
        {
            'type': 'ion',
            'dep_body': 'mars',
            'arr_body': 'vesta',
            'dep_date': '2009-02-17',
            'arr_date': '2011-07-16',
            'thrust_n': 0.092,
            'isp': 3000.0,
            'm0': m_dry_end_phase1,
            'm_dry': m_dry_end_phase2,
            'n_segments': 30,
        },
        # Phase 3: Vesta orbit phase (14 months)
        {
            'type': 'orbit',
            'body': 'vesta',
            'start_date': '2011-07-16',
            'end_date': '2012-09-05',
        },
        # Phase 4: Vesta→Ceres (ion cruise)
        {
            'type': 'ion',
            'dep_body': 'vesta',
            'arr_body': 'ceres',
            'dep_date': '2012-09-05',
            'arr_date': '2015-03-06',
            'thrust_n': 0.092,
            'isp': 3000.0,
            'm0': m_dry_end_phase2,
            'm_dry': m_dry_end_phase3,
            'n_segments': 30,
        },
        # Phase 5: Ceres orbit phase (end of mission)
        {
            'type': 'orbit',
            'body': 'ceres',
            'start_date': '2015-03-06',
            'end_date': '2018-10-31',
        },
    ]

    description = (
        'NASA Dawn mission (2007-2018). First spacecraft to orbit two extraterrestrial '
        'bodies — asteroid Vesta (2011-2012) and dwarf planet Ceres (2015-2018). '
        'Used NSTAR ion thrusters (92 mN, 3000s Isp) for all cruise propulsion. '
        'Mars gravity assist in 2009.'
    )

    return _build_mission_from_phases(
        phases, 'Dawn (NASA, 2007-2018)', description,
    )


# --- Asteroid element overrides for bodies not in our ephemeris ---
# Elements from JPL Small-Body Database (epoch JD 2460200.5 = 2023-09-13)

def build_hayabusa2_mission() -> Dict:
    """Hayabusa2 — Earth → Ryugu → Earth sample return (2014-2020).

    JAXA's successful sample return from C-type asteroid 162173 Ryugu.
    Used μ10 ion thrusters (8 mN × 4, up to 28 mN) for all interplanetary propulsion.
    Returned with 5.4 grams of asteroid material.

    Real event timeline:
      - Launch: 2014-12-03
      - Earth swing-by: 2015-12-03
      - Arrive Ryugu: 2018-06-27
      - First sample: 2019-02-22
      - Second sample: 2019-07-11
      - Depart Ryugu: 2019-11-13
      - Sample capsule return to Earth: 2020-12-06
    """
    m0 = 609.0   # launch mass
    m_dry_end_phase1 = 580.0  # after E→E GA (minimal propellant)
    m_dry_end_phase2 = 500.0  # after E→Ryugu (most propellant used)
    m_dry_end_phase3 = 400.0  # after Ryugu→Earth return

    phases = [
        # Phase 1: E→E gravity assist leg
        {
            'type': 'ion',
            'dep_body': 'earth',
            'arr_body': 'earth',
            'dep_date': '2014-12-03',
            'arr_date': '2015-12-03',
            'thrust_n': 0.028,
            'isp': 2900.0,
            'm0': m0,
            'm_dry': m_dry_end_phase1,
            'n_segments': 20,
        },
        # Phase 2: E→Ryugu ion cruise
        {
            'type': 'ion',
            'dep_body': 'earth',
            'arr_body': 'ryugu',
            'dep_date': '2015-12-03',
            'arr_date': '2018-06-27',
            'thrust_n': 0.028,
            'isp': 2900.0,
            'm0': m_dry_end_phase1,
            'm_dry': m_dry_end_phase2,
            'n_segments': 30,
        },
        # Phase 3: At Ryugu (1.5 years of operations)
        {
            'type': 'orbit',
            'body': 'ryugu',
            'start_date': '2018-06-27',
            'end_date': '2019-11-13',
        },
        # Phase 4: Ryugu→Earth return
        {
            'type': 'ion',
            'dep_body': 'ryugu',
            'arr_body': 'earth',
            'dep_date': '2019-11-13',
            'arr_date': '2020-12-06',
            'thrust_n': 0.028,
            'isp': 2900.0,
            'm0': m_dry_end_phase2,
            'm_dry': m_dry_end_phase3,
            'n_segments': 20,
        },
    ]

    description = (
        'JAXA Hayabusa2 sample return mission (2014-2020). Second successful '
        'asteroid sample return in history (after Hayabusa 1). Visited C-type '
        'asteroid 162173 Ryugu and returned 5.4 g of pristine samples to Earth. '
        'Used μ10 ion thrusters (28 mN, 2900s Isp) for all cruise propulsion.'
    )

    return _build_mission_from_phases(
        phases, 'Hayabusa2 (JAXA, 2014-2020)', description,
        element_overrides=_ASTEROID_ELEMENTS_EARLY,
    )


def build_hayabusa_mission() -> Dict:
    """Hayabusa — Earth → Itokawa → Earth sample return (2003-2010).

    JAXA's pioneering mission — the first spacecraft to return samples from an
    asteroid. Used 4 μ10 ion thrusters. Recovered 1500 dust grains from S-type
    asteroid 25143 Itokawa.

    Real event timeline:
      - Launch: 2003-05-09
      - Earth swing-by: 2004-05-19
      - Arrive Itokawa: 2005-09-12
      - Sample collection: 2005-11-25
      - Depart Itokawa: 2005-12-09
      - Return to Earth: 2010-06-13
    """
    m0 = 510.0
    m_dry_end_phase1 = 490.0
    m_dry_end_phase2 = 430.0
    m_dry_end_phase3 = 380.0

    phases = [
        {
            'type': 'ion',
            'dep_body': 'earth', 'arr_body': 'earth',
            'dep_date': '2003-05-09', 'arr_date': '2004-05-19',
            'thrust_n': 0.020, 'isp': 3200.0,
            'm0': m0, 'm_dry': m_dry_end_phase1,
            'n_segments': 20,
        },
        {
            'type': 'ion',
            'dep_body': 'earth', 'arr_body': 'itokawa',
            'dep_date': '2004-05-19', 'arr_date': '2005-09-12',
            'thrust_n': 0.020, 'isp': 3200.0,
            'm0': m_dry_end_phase1, 'm_dry': m_dry_end_phase2,
            'n_segments': 25,
        },
        {
            'type': 'orbit',
            'body': 'itokawa',
            'start_date': '2005-09-12', 'end_date': '2005-12-09',
        },
        {
            'type': 'ion',
            'dep_body': 'itokawa', 'arr_body': 'earth',
            'dep_date': '2005-12-09', 'arr_date': '2010-06-13',
            'thrust_n': 0.020, 'isp': 3200.0,
            'm0': m_dry_end_phase2, 'm_dry': m_dry_end_phase3,
            'n_segments': 35,
        },
    ]

    description = (
        'JAXA Hayabusa mission (2003-2010). First spacecraft to return '
        'asteroid samples to Earth. Visited S-type asteroid 25143 Itokawa '
        'and returned ~1500 dust grains. Used 4 μ10 ion thrusters (20 mN '
        'total, 3200s Isp). The mission survived multiple critical failures '
        'including ion thruster breakdowns and a crippled reaction wheel.'
    )

    return _build_mission_from_phases(
        phases, 'Hayabusa (JAXA, 2003-2010)', description,
        element_overrides=_ASTEROID_ELEMENTS_EARLY,
    )


def build_bepi_colombo_mission() -> Dict:
    """BepiColombo — Earth → Mercury with 9 gravity assists (2018-2025).

    ESA/JAXA hybrid mission to Mercury. Longest and most complex Mercury
    trajectory ever: 1 Earth flyby, 2 Venus flybys, 6 Mercury flybys, then
    orbit insertion via chemical bi-prop.

    Real event timeline (simplified):
      - Launch: 2018-10-19
      - Earth flyby: 2020-04-10
      - Venus flyby 1: 2020-10-15
      - Venus flyby 2: 2021-08-10
      - Mercury flyby 1: 2021-10-01
      - Mercury flyby 2: 2022-06-23
      - Mercury flyby 3: 2023-06-19
      - Mercury flyby 4: 2024-09-04
      - Mercury flyby 5: 2024-12-01
      - Mercury flyby 6: 2025-01-08
      - Mercury orbit insertion: 2025-12-05
    """
    # BepiColombo masses decrease significantly due to ion + chemical usage
    # Launch mass: 4100 kg; MTM (transfer module) carries 580 kg of xenon + chem
    m_series = [4100, 3900, 3700, 3550, 3400, 3300, 3200, 3100, 3050, 3000, 2950, 2800]

    # Segments: Launch → Earth → Venus → Venus → Mercury × 6 → Mercury orbit
    dates = [
        '2018-10-19', '2020-04-10', '2020-10-15', '2021-08-10',
        '2021-10-01', '2022-06-23', '2023-06-19', '2024-09-04',
        '2024-12-01', '2025-01-08', '2025-12-05',
    ]
    bodies = [
        'earth', 'earth', 'venus', 'venus',
        'mercury', 'mercury', 'mercury', 'mercury',
        'mercury', 'mercury', 'mercury',
    ]

    phases = []
    for i in range(len(dates) - 1):
        phases.append({
            'type': 'ion',
            'dep_body': bodies[i],
            'arr_body': bodies[i + 1],
            'dep_date': dates[i],
            'arr_date': dates[i + 1],
            'thrust_n': 0.145,
            'isp': 4300.0,
            'm0': m_series[i],
            'm_dry': m_series[i + 1],
            'n_segments': 25 if (dates[i] == '2018-10-19' or bodies[i] == 'venus') else 15,
        })

    description = (
        'ESA/JAXA BepiColombo mission (2018-2025, arrival). Hybrid mission '
        'using T6 ion thrusters (145 mN, 4300s Isp) plus chemical bi-prop. '
        'Most complex gravity-assist chain ever flown to Mercury: 1 Earth '
        'flyby + 2 Venus flybys + 6 Mercury flybys to match Mercury\'s orbital '
        'velocity. Two spacecraft (MPO + MMO) arrive at Mercury in late 2025.'
    )

    return _build_mission_from_phases(
        phases, 'BepiColombo (ESA/JAXA, 2018-2025)', description,
    )


def build_psyche_mission() -> Dict:
    """NASA Psyche — Earth → Mars gravity assist → (16) Psyche (2023-2029).

    Mission to the unique M-type asteroid Psyche, possibly an exposed planetary core.
    Uses SPT-140 Hall-effect thrusters (first deep-space Hall thrusters).

    Real event timeline:
      - Launch: 2023-10-13
      - Mars gravity assist: 2026-05-?? (flyby)
      - Arrive Psyche: 2029-07-?? (orbit insertion)
      - Mission extends through 2031+
    """
    m0 = 2608.0
    m_dry_end_phase1 = 2400.0
    m_dry_end_phase2 = 2100.0

    phases = [
        {
            'type': 'ion',
            'dep_body': 'earth', 'arr_body': 'mars',
            'dep_date': '2023-10-13', 'arr_date': '2026-05-15',
            'thrust_n': 0.280, 'isp': 2500.0,  # SPT-140 at medium Isp
            'm0': m0, 'm_dry': m_dry_end_phase1,
            'n_segments': 30,
        },
        {
            'type': 'ion',
            'dep_body': 'mars', 'arr_body': 'psyche',
            'dep_date': '2026-05-15', 'arr_date': '2029-07-15',
            'thrust_n': 0.280, 'isp': 2500.0,
            'm0': m_dry_end_phase1, 'm_dry': m_dry_end_phase2,
            'n_segments': 35,
        },
        {
            'type': 'orbit',
            'body': 'psyche',
            'start_date': '2029-07-15', 'end_date': '2031-10-01',
        },
    ]

    description = (
        'NASA Psyche mission (2023-2029 arrival). First deep-space mission '
        'using Hall-effect thrusters (SPT-140, 280 mN, 2500s Isp). Target is '
        '16 Psyche, a ~220 km M-type asteroid believed to be an exposed iron-nickel '
        'planetary core. Launched 2023-10-13, Mars gravity assist 2026, '
        'Psyche orbit insertion 2029-07.'
    )

    return _build_mission_from_phases(
        phases, 'Psyche (NASA, 2023-2029)', description,
        element_overrides=_ASTEROID_ELEMENTS_EARLY,
    )


def build_ikaros_mission() -> Dict:
    """JAXA IKAROS — first interplanetary solar sail with Venus flyby (2010).

    IKAROS (Interplanetary Kite-craft Accelerated by Radiation Of the Sun)
    was the first spacecraft to successfully demonstrate solar sail propulsion
    in interplanetary space. 14m × 14m square sail.

    Real event timeline:
      - Launch: 2010-05-21 (piggyback with Akatsuki to Venus)
      - Sail deployment: 2010-06-09 (at ~0.7 AU)
      - Venus flyby: 2010-12-08
      - Extended mission continued until ~2015 (contact lost)

    IKAROS effectively coasted to Venus (launched on a Venus trajectory)
    with the sail providing small accelerations. For visualization, model
    as a ballistic E→Venus trajectory (since sail thrust was small relative
    to the trajectory already set by the launcher).
    """
    phases = [
        # Leg 1: Earth → Venus flyby (ballistic since the launch put IKAROS on a
        # direct Venus trajectory; sail thrust refined it)
        {
            'type': 'ballistic',
            'dep_body': 'earth',
            'arr_body': 'venus',
            'dep_date': '2010-05-21',
            'arr_date': '2010-12-08',
        },
    ]

    description = (
        'JAXA IKAROS (2010-2015). The first spacecraft to successfully '
        'demonstrate solar sail propulsion in interplanetary space. Deployed '
        'a 14m × 14m square sail with liquid-crystal attitude controllers. '
        'Launched with Akatsuki toward Venus, IKAROS used its sail to refine '
        'the trajectory during the 6-month cruise. Successfully performed a '
        'Venus flyby on 2010-12-08. Extended mission continued until 2015.'
    )

    return _build_mission_from_phases(
        phases, 'IKAROS (JAXA, 2010)', description,
    )


def _build_mission_from_phases(phases: List[Dict],
                                mission_name: str,
                                description: str,
                                element_overrides: Dict = None) -> Dict:
    """Build a complete mission from a list of phase specs.

    Each phase is one of:
      {'type': 'ion', dep_body, arr_body, dep_date, arr_date, thrust_n, isp, m0, m_dry, [n_segments]}
      {'type': 'ballistic', dep_body, arr_body, dep_date, arr_date}
      {'type': 'orbit', body, start_date, end_date}
    """
    all_positions = []
    events = []
    sequence = []
    total_propellant = 0.0
    total_ion_dv = 0.0
    final_mass = None

    for i, phase in enumerate(phases):
        if phase['type'] == 'ion':
            result = _propagate_ion_leg(
                phase['dep_body'], phase['arr_body'],
                phase['dep_date'], phase['arr_date'],
                phase['thrust_n'], phase['isp'],
                phase['m0'], phase['m_dry'],
                n_segments=phase.get('n_segments', 20),
                element_overrides=element_overrides,
            )
            positions = result['positions']
            total_propellant += result['propellant_kg']
            total_ion_dv += result['ion_dv']
            final_mass = result['final_mass_kg']

            if i == 0 or not events:
                events.append({
                    'body': phase['dep_body'].title(),
                    'date': phase['dep_date'],
                    'type': 'launch',
                    'distance_km': 0,
                    'dv_gained_km_s': 0.0,
                    'heliocentric_position_km': positions[0] if positions else [0, 0, 0],
                })
                sequence.append(phase['dep_body'].title())

            events.append({
                'body': phase['arr_body'].title(),
                'date': phase['arr_date'],
                'type': 'flyby' if i < len(phases) - 1 else 'arrival',
                'distance_km': 0,
                'dv_gained_km_s': round(result['ion_dv'], 2),
                'heliocentric_position_km': positions[-1] if positions else [0, 0, 0],
            })
            sequence.append(phase['arr_body'].title())
            all_positions.extend(positions)

        elif phase['type'] == 'ballistic':
            result = _propagate_ballistic_leg(
                phase['dep_body'], phase['arr_body'],
                phase['dep_date'], phase['arr_date'],
                element_overrides=element_overrides,
            )
            positions = result['positions']

            if i == 0 or not events:
                events.append({
                    'body': phase['dep_body'].title(),
                    'date': phase['dep_date'],
                    'type': 'launch',
                    'distance_km': 0,
                    'dv_gained_km_s': 0.0,
                    'heliocentric_position_km': positions[0] if positions else [0, 0, 0],
                })
                sequence.append(phase['dep_body'].title())

            events.append({
                'body': phase['arr_body'].title(),
                'date': phase['arr_date'],
                'type': 'flyby' if i < len(phases) - 1 else 'arrival',
                'distance_km': 0,
                'dv_gained_km_s': 0.0,
                'heliocentric_position_km': positions[-1] if positions else [0, 0, 0],
            })
            sequence.append(phase['arr_body'].title())
            all_positions.extend(positions)

        elif phase['type'] == 'orbit':
            # Follow the body from start to end
            positions = _follow_body(
                phase['body'], phase['start_date'], phase['end_date'],
                n_points=50, element_overrides=element_overrides,
            )
            all_positions.extend(positions)

            # If the previous event was arriving at this body, change it to "arrival"
            if events and events[-1]['body'].lower() == phase['body'].lower():
                events[-1]['type'] = 'arrival'

            # Add an "end of orbit" event at the end date
            is_last_phase = (i == len(phases) - 1)
            if is_last_phase or (i + 1 < len(phases) and
                                 phases[i + 1].get('type') != 'orbit'):
                events.append({
                    'body': phase['body'].title(),
                    'date': phase['end_date'],
                    'type': 'arrival' if is_last_phase else 'flyby',
                    'distance_km': 0,
                    'dv_gained_km_s': 0.0,
                    'heliocentric_position_km': positions[-1] if positions else [0, 0, 0],
                })

    return {
        'name': mission_name,
        'description': description,
        'sequence': sequence,
        'events': events,
        'trajectory_positions': all_positions,
        'stats': {
            'total_propellant_kg': round(total_propellant, 1) if total_propellant > 0 else 0,
            'total_ion_dv_km_s': round(total_ion_dv, 3) if total_ion_dv > 0 else 0,
            'final_mass_kg': round(final_mass, 1) if final_mass else None,
            'n_phases': len(phases),
        },
    }
