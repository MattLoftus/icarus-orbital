"""Solar sail trajectory optimization.

Physics: thrust is continuous radiation pressure, always pointing away from
the Sun (cannot thrust toward the Sun). Thrust magnitude scales as 1/r².
Control variable: sail orientation (cone + clock angles).

Ideal sail model (flat, perfectly reflective):
    F = (2*P0*A/c) * (r0/r)² * cos²(α) * n̂

where:
    P0 = solar flux at 1 AU ≈ 1361 W/m² / c ≈ 4.54e-6 N/m² radiation pressure
    A = sail area (m²)
    c = speed of light (m/s) — absorbed into P0 as momentum flux
    r0 = 1 AU
    r = distance from Sun
    α = cone angle (angle between sail normal and sun-sat line)
    n̂ = sail normal direction

The key figure of merit is the "characteristic acceleration" at 1 AU:
    a_c = 2 * P0 * A / m  (at perfect reflection, α=0)

Typical values: 0.1–1.0 mm/s² for current technology, ambitious missions.

For trajectory integration, we use a numerical RK4 integrator since Kepler
propagation isn't possible with continuous thrust.
"""

import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

from .jpl_lp import jpl_lp_state, GTOP_MU_SUN, GTOP_AU_KM


# Solar radiation pressure at 1 AU: ~4.54e-6 N/m² × c / c ≈ 4.54e-6 N/m²
# For a perfectly reflective sail at α=0, thrust = 2 × P × A (radiation bounces back)
# Characteristic acceleration a_c = 2 * P0 * A / m at 1 AU, pointing away from Sun
# We parameterize missions by a_c (mm/s²) rather than A and m separately.

_P0_NM2 = 4.5636e-6  # N/m² at 1 AU (solar radiation pressure)
_AU_M = GTOP_AU_KM * 1000.0
_MU_SUN_M3S2 = GTOP_MU_SUN * 1e9  # km³/s² → m³/s²


def _sail_acceleration(r_m: np.ndarray, v_m: np.ndarray, ac_ms2: float,
                       cone_angle: float, clock_angle: float) -> np.ndarray:
    """Compute solar sail acceleration in SI units (m/s²).

    Args:
        r_m: position vector (m), heliocentric
        v_m: velocity vector (m/s), heliocentric (used to build local frame)
        ac_ms2: characteristic acceleration at 1 AU (m/s²)
        cone_angle: angle from sun-sat line to sail normal (rad), 0 = max thrust outward
        clock_angle: rotation of normal around sun-sat line (rad)

    Returns:
        Acceleration vector (m/s²) in heliocentric frame.
    """
    r_mag = np.linalg.norm(r_m)
    if r_mag < 1e3:
        return np.zeros(3)

    # Sun-sat unit vector (from Sun toward sailcraft — the "radial outward" direction)
    rhat = r_m / r_mag

    # Local frame: rhat (radial), vhat (along motion), nhat (out of plane)
    vhat_proj = v_m - np.dot(v_m, rhat) * rhat
    vhat_norm = np.linalg.norm(vhat_proj)
    if vhat_norm < 1e-6:
        # Degenerate — spacecraft moving radially; pick arbitrary transverse
        tmp = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(tmp, rhat)) > 0.99:
            tmp = np.array([1.0, 0.0, 0.0])
        vhat = np.cross(rhat, tmp)
        vhat = vhat / np.linalg.norm(vhat)
    else:
        vhat = vhat_proj / vhat_norm
    nhat = np.cross(rhat, vhat)

    # Sail normal in local frame: angle cone from rhat, rotated by clock around rhat
    sn = (np.cos(cone_angle) * rhat
          + np.sin(cone_angle) * np.cos(clock_angle) * vhat
          + np.sin(cone_angle) * np.sin(clock_angle) * nhat)

    # Thrust only if sail normal has positive component along sun direction
    # (sail must face toward Sun to catch photons)
    cos_alpha = np.dot(sn, rhat)
    if cos_alpha <= 0:
        return np.zeros(3)

    # Ideal sail thrust: a = a_c * (r0/r)² * cos²(α) * n̂
    factor = ac_ms2 * (_AU_M / r_mag) ** 2 * cos_alpha ** 2
    return factor * sn


def _dynamics(state: np.ndarray, ac_ms2: float,
              cone_angle: float, clock_angle: float) -> np.ndarray:
    """Equations of motion: dr/dt = v; dv/dt = -μ/r³ r + a_sail."""
    r = state[:3]
    v = state[3:]
    r_mag = np.linalg.norm(r)
    if r_mag < 1e3:
        return np.zeros(6)
    a_grav = -_MU_SUN_M3S2 / (r_mag ** 3) * r
    a_sail = _sail_acceleration(r, v, ac_ms2, cone_angle, clock_angle)
    return np.concatenate([v, a_grav + a_sail])


def _rk4_step(state: np.ndarray, dt: float, ac_ms2: float,
              cone_angle: float, clock_angle: float) -> np.ndarray:
    """Single RK4 integration step."""
    k1 = _dynamics(state, ac_ms2, cone_angle, clock_angle)
    k2 = _dynamics(state + 0.5 * dt * k1, ac_ms2, cone_angle, clock_angle)
    k3 = _dynamics(state + 0.5 * dt * k2, ac_ms2, cone_angle, clock_angle)
    k4 = _dynamics(state + dt * k3, ac_ms2, cone_angle, clock_angle)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def propagate_solar_sail(r0_km: np.ndarray, v0_kms: np.ndarray,
                          duration_days: float, ac_ms2: float,
                          control_schedule,
                          n_steps: int = 2000) -> Tuple[List, List]:
    """Propagate a solar sail trajectory with time-varying sail orientation.

    Args:
        r0_km: initial position (km)
        v0_kms: initial velocity (km/s)
        duration_days: total TOF (days)
        ac_ms2: characteristic acceleration at 1 AU (m/s²)
        control_schedule: callable(t_frac) -> (cone_angle, clock_angle), where t_frac ∈ [0, 1]
        n_steps: number of RK4 steps

    Returns:
        (positions_km, velocities_kms) lists, length n_steps+1
    """
    # Convert to SI for integration
    r = r0_km * 1000.0
    v = v0_kms * 1000.0
    state = np.concatenate([r, v])

    total_sec = duration_days * 86400.0
    dt = total_sec / n_steps

    positions_km = [r0_km.tolist()]
    velocities_kms = [v0_kms.tolist()]

    for i in range(n_steps):
        t_frac = i / n_steps
        cone, clock = control_schedule(t_frac)
        state = _rk4_step(state, dt, ac_ms2, cone, clock)
        positions_km.append((state[:3] / 1000.0).tolist())
        velocities_kms.append((state[3:] / 1000.0).tolist())

    return positions_km, velocities_kms


def _locally_optimal_control(r_m, v_m, target_mode: str = 'outward'):
    """Compute locally optimal sail orientation for a given goal.

    target_mode:
        'outward': maximize radial (heliocentric) acceleration — for escape
        'orbital_energy': maximize orbital energy rate (tangential thrust)
        'inward': minimize orbital energy (for inward spiral)
        'crank_inclination': crank heliocentric inclination (out-of-plane thrust)
    """
    r_mag = np.linalg.norm(r_m)
    rhat = r_m / r_mag
    vhat_proj = v_m - np.dot(v_m, rhat) * rhat
    vhat_norm = np.linalg.norm(vhat_proj)
    if vhat_norm < 1e-6:
        return 0.0, 0.0

    if target_mode == 'outward':
        return 0.0, 0.0
    elif target_mode == 'orbital_energy':
        return 0.6155, 0.0
    elif target_mode == 'inward':
        return 0.6155, np.pi
    elif target_mode == 'crank_inclination':
        # Thrust perpendicular to the current orbital plane (out-of-plane).
        # In our local frame: i=rhat, j=vhat_proj (tangential), k=i×j (out of plane).
        # To max inclination change, thrust perpendicular to both r and v — i.e., along k.
        # Sail normal at cone=35.26° toward k direction, clock=±π/2 aligns with nhat.
        # Alternate sign each half-orbit (ascending vs descending node) for net inclination change.
        # Sign: thrust should point in the direction of orbital angular momentum's
        # rotation axis when crossing ascending node, opposite at descending.
        # Use sign of (r × v)·ẑ to determine half-orbit.
        # Simpler: use clock = +π/2 when above ecliptic, -π/2 when below.
        clock = np.pi / 2 if r_m[2] > 0 else -np.pi / 2
        return 0.6155, clock
    return 0.0, 0.0


def solar_sail_escape(dep_date: str, ac_ms2: float,
                       duration_years: float = 15.0,
                       n_steps: int = 4000,
                       strategy: str = 'sundiver') -> Dict:
    """Solar sail escape trajectory from Earth: maximize heliocentric escape velocity.

    Strategies:
        'outward': always thrust tangentially to increase orbital energy
        'sundiver': brake initially to fall toward Sun (Oberth effect at perihelion),
                    then accelerate outward. Achieves higher asymptotic v_inf for
                    a given a_c by exploiting the deep gravity well.
    """
    # Parse date → MJD2000
    base = datetime(2000, 1, 1)
    dep = datetime.fromisoformat(dep_date)
    t0_mjd = (dep - base).total_seconds() / 86400.0

    # Start from Earth state (launch velocity equals Earth's velocity — pure sail)
    r_e = jpl_lp_state('earth', t0_mjd)
    r0_km = r_e[:3]
    v0_kms = r_e[3:]

    # Custom propagation that updates control based on current state
    r = r0_km * 1000.0
    v = v0_kms * 1000.0
    state = np.concatenate([r, v])

    total_sec = duration_years * 365.25 * 86400
    dt = total_sec / n_steps

    positions_km = [r0_km.tolist()]
    energies = []
    phase_log = []  # track phase (braking/accelerating)

    # For sundiver: detect perihelion (radial velocity crosses from negative to positive)
    prev_vr = 0.0
    perihelion_hit = False

    for i in range(n_steps):
        r_vec = state[:3]
        v_vec = state[3:]
        r_mag_m = np.linalg.norm(r_vec)
        rhat = r_vec / r_mag_m
        vr = float(np.dot(v_vec, rhat))  # radial velocity

        if strategy == 'sundiver':
            # Phase 1: radial velocity is inward (vr < 0) or not yet perihelion → brake
            # Phase 2: after perihelion → accelerate
            if not perihelion_hit and vr >= 0 and prev_vr < 0:
                perihelion_hit = True
            if not perihelion_hit:
                # Brake: thrust opposite to velocity → decelerate, fall inward
                cone, clock = 0.6155, np.pi  # 35.26° cone, clock π (retrograde tangential)
                phase_log.append('brake')
            else:
                # Accelerate: thrust along velocity → spiral out
                cone, clock = 0.6155, 0.0
                phase_log.append('accel')
            prev_vr = vr
        else:  # 'outward'
            cone, clock = 0.6155, 0.0
            phase_log.append('accel')

        state = _rk4_step(state, dt, ac_ms2, cone, clock)
        positions_km.append((state[:3] / 1000.0).tolist())

        v_mag_m = np.linalg.norm(state[3:])
        r_mag_m = np.linalg.norm(state[:3])
        energy = 0.5 * v_mag_m ** 2 - _MU_SUN_M3S2 / r_mag_m
        energies.append(energy)

    # Asymptotic escape velocity
    final_energy = energies[-1]
    v_inf_escape_ms = np.sqrt(2 * final_energy) if final_energy > 0 else 0.0
    v_inf_escape_kms = v_inf_escape_ms / 1000.0

    # Time to escape the solar system (positive energy)
    t_escape_idx = None
    for i, e in enumerate(energies):
        if e > 0:
            t_escape_idx = i
            break
    escape_date_mjd = t0_mjd + (t_escape_idx / n_steps * duration_years * 365.25) if t_escape_idx else None

    return {
        'positions_km': positions_km,
        'departure_mjd2000': t0_mjd,
        'duration_years': duration_years,
        'ac_mm_s2': ac_ms2 * 1e3,  # convert m/s² → mm/s²
        'final_energy_J_per_kg': final_energy,
        'v_inf_escape_km_s': v_inf_escape_kms,
        'v_inf_escape_au_per_year': v_inf_escape_kms * 86400 * 365.25 / GTOP_AU_KM,
        'escape_time_years': (t_escape_idx / n_steps * duration_years) if t_escape_idx else None,
        'escape_date_mjd2000': escape_date_mjd,
        'n_points': len(positions_km),
    }


def solar_polar_observer(dep_date: str, ac_ms2: float,
                          duration_years: float = 8.0,
                          n_steps: int = 6000) -> Dict:
    """Solar sail mission to crank heliocentric inclination.

    Strategy: continuous out-of-plane thrust (perpendicular to orbital plane),
    alternating direction each half-orbit to accumulate inclination change.
    Near-Sun orbit at 0.5 AU is efficient since thrust scales as 1/r².

    Typical advanced sail (a_c ~ 2 mm/s²) can reach 75° inclination in ~7-8 years.
    """
    base = datetime(2000, 1, 1)
    dep = datetime.fromisoformat(dep_date)
    t0_mjd = (dep - base).total_seconds() / 86400.0

    r_e = jpl_lp_state('earth', t0_mjd)
    r0_km = r_e[:3]
    v0_kms = r_e[3:]

    r = r0_km * 1000.0
    v = v0_kms * 1000.0
    state = np.concatenate([r, v])

    total_sec = duration_years * 365.25 * 86400
    dt = total_sec / n_steps

    positions_km = [r0_km.tolist()]
    inclinations = []

    # Phase 1: spiral inward to ~0.5 AU for efficient inclination cranking
    # Phase 2: crank inclination
    # Use distance threshold to switch phases.
    target_r_for_cranking_au = 0.5

    for i in range(n_steps):
        r_mag = np.linalg.norm(state[:3])
        r_au = r_mag / _AU_M

        # Compute current inclination from state
        r_vec = state[:3]
        v_vec = state[3:]
        h = np.cross(r_vec, v_vec)
        h_mag = np.linalg.norm(h)
        cos_i = h[2] / h_mag if h_mag > 0 else 1.0
        cos_i = max(-1.0, min(1.0, cos_i))
        current_inc_deg = np.degrees(np.arccos(cos_i))
        inclinations.append(current_inc_deg)

        # Phase logic: inward first, then crank
        if r_au > target_r_for_cranking_au and current_inc_deg < 2.0:
            # Phase 1: spiral inward
            cone, clock = _locally_optimal_control(state[:3], state[3:], 'inward')
        else:
            # Phase 2: crank inclination
            cone, clock = _locally_optimal_control(state[:3], state[3:], 'crank_inclination')

        state = _rk4_step(state, dt, ac_ms2, cone, clock)
        positions_km.append((state[:3] / 1000.0).tolist())

    final_inc = inclinations[-1]
    final_r_au = np.linalg.norm(state[:3]) / _AU_M

    return {
        'positions_km': positions_km,
        'inclinations_deg': inclinations,
        'departure_mjd2000': t0_mjd,
        'duration_years': duration_years,
        'ac_mm_s2': ac_ms2 * 1e3,
        'final_inclination_deg': float(final_inc),
        'peak_inclination_deg': float(max(inclinations)),
        'final_r_au': float(final_r_au),
        'n_points': len(positions_km),
    }


def propagate_solar_polar_observer_mission(dep_date: str, ac_ms2: float,
                                            duration_years: float = 8.0) -> Dict:
    """Format a solar polar observer mission for the designed_missions viewer."""
    result = solar_polar_observer(dep_date, ac_ms2, duration_years=duration_years, n_steps=4000)

    base = datetime(2000, 1, 1)
    t0_mjd = result['departure_mjd2000']
    arrive_mjd = t0_mjd + duration_years * 365.25

    def fmt(mjd):
        return (base + timedelta(days=float(mjd))).strftime('%Y-%m-%d')

    events = [
        {
            'body': 'Earth',
            'date': fmt(t0_mjd),
            'type': 'launch',
            'distance_km': 0,
            'dv_gained_km_s': 0.0,
            'heliocentric_position_km': result['positions_km'][0],
        },
        {
            'body': f'Polar Orbit ({result["peak_inclination_deg"]:.0f}° inclination)',
            'date': fmt(arrive_mjd),
            'type': 'arrival',
            'distance_km': 0,
            'dv_gained_km_s': round(float(result['peak_inclination_deg']), 1),
            'heliocentric_position_km': result['positions_km'][-1],
        },
    ]

    return {
        'events': events,
        'trajectory_positions': result['positions_km'],
        'sequence': ['Earth', 'Solar Polar Orbit'],
        'stats': {
            'propulsion_type': 'solar_sail',
            'characteristic_acceleration_mm_s2': round(float(result['ac_mm_s2']), 3),
            'peak_inclination_deg': round(float(result['peak_inclination_deg']), 1),
            'final_inclination_deg': round(float(result['final_inclination_deg']), 1),
            'final_r_au': round(float(result['final_r_au']), 2),
            'duration_years': duration_years,
            'no_propellant': True,
        },
    }


def propagate_solar_sail_escape_mission(dep_date: str, ac_ms2: float,
                                         duration_years: float = 15.0) -> Dict:
    """Format a solar sail escape mission for the designed_missions viewer."""
    result = solar_sail_escape(dep_date, ac_ms2, duration_years=duration_years, n_steps=3000)

    base = datetime(2000, 1, 1)
    t0_mjd = result['departure_mjd2000']
    arrive_mjd = t0_mjd + duration_years * 365.25

    def fmt(mjd):
        return (base + timedelta(days=float(mjd))).strftime('%Y-%m-%d')

    events = [
        {
            'body': 'Earth',
            'date': fmt(t0_mjd),
            'type': 'launch',
            'distance_km': 0,
            'dv_gained_km_s': 0.0,
            'heliocentric_position_km': result['positions_km'][0],
        },
    ]
    if result['escape_time_years'] is not None:
        escape_idx = int(result['escape_time_years'] / duration_years * len(result['positions_km']))
        escape_idx = min(escape_idx, len(result['positions_km']) - 1)
        events.append({
            'body': 'Solar System Escape',
            'date': fmt(t0_mjd + result['escape_time_years'] * 365.25),
            'type': 'flyby',
            'distance_km': 0,
            'dv_gained_km_s': 0.0,
            'heliocentric_position_km': result['positions_km'][escape_idx],
        })

    # Final arrival
    events.append({
        'body': f'Cruise ({result["v_inf_escape_km_s"]:.1f} km/s asymptotic)',
        'date': fmt(arrive_mjd),
        'type': 'arrival',
        'distance_km': 0,
        'dv_gained_km_s': round(float(result['v_inf_escape_km_s']), 2),
        'heliocentric_position_km': result['positions_km'][-1],
    })

    return {
        'events': events,
        'trajectory_positions': result['positions_km'],
        'sequence': ['Earth', 'Escape'],
        'stats': {
            'propulsion_type': 'solar_sail',
            'characteristic_acceleration_mm_s2': round(float(result['ac_mm_s2']), 3),
            'v_inf_escape_km_s': round(float(result['v_inf_escape_km_s']), 2),
            'v_inf_escape_au_per_year': round(float(result['v_inf_escape_au_per_year']), 2),
            'escape_time_years': round(float(result['escape_time_years']), 2) if result['escape_time_years'] is not None else None,
            'duration_years': duration_years,
            'no_propellant': True,
        },
    }
