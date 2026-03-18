"""Keplerian orbit position from classical orbital elements.

Given orbital elements (a, e, i, Ω, ω, M₀) and an epoch, compute
heliocentric position [x, y, z] at any date. This enables asteroid
trajectory computation without SPICE kernels — we only need the
orbital elements from JPL's Small-Body Database.
"""

import numpy as np
from typing import Tuple
from .constants import MU_SUN


# 1 AU in km
AU_KM = 1.495978707e8


def solve_kepler_equation(M: float, e: float, tol: float = 1e-12) -> float:
    """Solve Kepler's equation M = E - e*sin(E) for eccentric anomaly E.

    Uses Newton-Raphson iteration. Works for elliptic orbits (e < 1).
    For hyperbolic orbits (e > 1), solves M = e*sinh(H) - H.

    Args:
        M: Mean anomaly (radians)
        e: Eccentricity
        tol: Convergence tolerance

    Returns:
        E: Eccentric anomaly (radians) for e < 1
        H: Hyperbolic anomaly (radians) for e > 1
    """
    if e < 1.0:
        # Elliptic: M = E - e*sin(E)
        E = M + e * np.sin(M) if e < 0.8 else np.pi  # initial guess
        for _ in range(50):
            dE = (M - E + e * np.sin(E)) / (1 - e * np.cos(E))
            E += dE
            if abs(dE) < tol:
                break
        return E
    else:
        # Hyperbolic: M = e*sinh(H) - H
        H = M  # initial guess
        for _ in range(50):
            dH = (M - e * np.sinh(H) + H) / (e * np.cosh(H) - 1)
            H += dH
            if abs(dH) < tol:
                break
        return H


def elements_to_position(a_au: float, e: float, i_deg: float,
                         om_deg: float, w_deg: float, M_rad: float
                         ) -> np.ndarray:
    """Convert orbital elements to heliocentric position in ecliptic J2000.

    Args:
        a_au: Semi-major axis (AU)
        e: Eccentricity
        i_deg: Inclination (degrees)
        om_deg: Longitude of ascending node (degrees)
        w_deg: Argument of periapsis (degrees)
        M_rad: Mean anomaly (radians)

    Returns:
        Position [x, y, z] in km (ecliptic J2000, heliocentric)
    """
    a = a_au * AU_KM  # km

    # Solve Kepler's equation for eccentric/hyperbolic anomaly
    if e < 1.0:
        E = solve_kepler_equation(M_rad, e)
        # True anomaly from eccentric anomaly
        nu = 2 * np.arctan2(
            np.sqrt(1 + e) * np.sin(E / 2),
            np.sqrt(1 - e) * np.cos(E / 2)
        )
        # Distance
        r = a * (1 - e * np.cos(E))
    else:
        H = solve_kepler_equation(M_rad, e)
        nu = 2 * np.arctan2(
            np.sqrt(e + 1) * np.sinh(H / 2),
            np.sqrt(e - 1) * np.cosh(H / 2)
        )
        r = a * (1 - e * np.cosh(H))
        r = abs(r)

    # Position in orbital plane
    x_orb = r * np.cos(nu)
    y_orb = r * np.sin(nu)

    # Convert angles to radians
    i = np.radians(i_deg)
    om = np.radians(om_deg)
    w = np.radians(w_deg)

    # Rotation matrix: orbital plane → ecliptic J2000
    cos_om, sin_om = np.cos(om), np.sin(om)
    cos_w, sin_w = np.cos(w), np.sin(w)
    cos_i, sin_i = np.cos(i), np.sin(i)

    # Combined rotation: R_z(-Ω) * R_x(-i) * R_z(-ω)
    x = (cos_om * (cos_w * x_orb - sin_w * y_orb) -
         sin_om * (sin_w * x_orb + cos_w * y_orb) * cos_i)
    y = (sin_om * (cos_w * x_orb - sin_w * y_orb) +
         cos_om * (sin_w * x_orb + cos_w * y_orb) * cos_i)
    z = (sin_w * x_orb + cos_w * y_orb) * sin_i

    return np.array([x, y, z])


def elements_to_state(a_au: float, e: float, i_deg: float,
                      om_deg: float, w_deg: float, M_rad: float
                      ) -> np.ndarray:
    """Convert orbital elements to heliocentric state [x,y,z,vx,vy,vz] in ecliptic J2000.

    Returns position (km) and velocity (km/s).
    """
    a = a_au * AU_KM
    mu = MU_SUN

    if e < 1.0:
        E = solve_kepler_equation(M_rad, e)
        nu = 2 * np.arctan2(
            np.sqrt(1 + e) * np.sin(E / 2),
            np.sqrt(1 - e) * np.cos(E / 2)
        )
        r = a * (1 - e * np.cos(E))
    else:
        H = solve_kepler_equation(M_rad, e)
        nu = 2 * np.arctan2(
            np.sqrt(e + 1) * np.sinh(H / 2),
            np.sqrt(e - 1) * np.cosh(H / 2)
        )
        r = abs(a * (1 - e * np.cosh(H)))

    # Semi-latus rectum
    p = a * (1 - e**2) if e < 1.0 else abs(a) * (e**2 - 1)

    # Position and velocity in orbital plane
    x_orb = r * np.cos(nu)
    y_orb = r * np.sin(nu)
    h = np.sqrt(mu * p)  # specific angular momentum
    vx_orb = -mu / h * np.sin(nu)
    vy_orb = mu / h * (e + np.cos(nu))

    # Rotation to ecliptic J2000
    i = np.radians(i_deg)
    om = np.radians(om_deg)
    w = np.radians(w_deg)

    cos_om, sin_om = np.cos(om), np.sin(om)
    cos_w, sin_w = np.cos(w), np.sin(w)
    cos_i, sin_i = np.cos(i), np.sin(i)

    def rotate(xo, yo):
        x = cos_om * (cos_w * xo - sin_w * yo) - sin_om * (sin_w * xo + cos_w * yo) * cos_i
        y = sin_om * (cos_w * xo - sin_w * yo) + cos_om * (sin_w * xo + cos_w * yo) * cos_i
        z = (sin_w * xo + cos_w * yo) * sin_i
        return x, y, z

    px, py, pz = rotate(x_orb, y_orb)
    vx, vy, vz = rotate(vx_orb, vy_orb)

    return np.array([px, py, pz, vx, vy, vz])


def propagate_from_elements(a_au: float, e: float, i_deg: float,
                            om_deg: float, w_deg: float,
                            ma_deg: float, epoch_jd: float,
                            target_jd: float) -> np.ndarray:
    """Compute position at target_jd given elements at epoch_jd.

    Args:
        a_au: Semi-major axis (AU)
        e: Eccentricity
        i_deg: Inclination (degrees)
        om_deg: RAAN (degrees)
        w_deg: Argument of periapsis (degrees)
        ma_deg: Mean anomaly at epoch (degrees)
        epoch_jd: Julian date of orbital elements
        target_jd: Julian date to compute position at

    Returns:
        Position [x, y, z] in km (ecliptic J2000)
    """
    a_km = a_au * AU_KM

    # Mean motion (rad/day)
    period_sec = 2 * np.pi * np.sqrt(a_km**3 / MU_SUN)
    n = 2 * np.pi / (period_sec / 86400)  # rad/day

    # Propagate mean anomaly
    dt_days = target_jd - epoch_jd
    M = np.radians(ma_deg) + n * dt_days
    M = M % (2 * np.pi)

    return elements_to_position(a_au, e, i_deg, om_deg, w_deg, M)


def propagate_state_from_elements(a_au: float, e: float, i_deg: float,
                                  om_deg: float, w_deg: float,
                                  ma_deg: float, epoch_jd: float,
                                  target_jd: float) -> np.ndarray:
    """Compute full state [x,y,z,vx,vy,vz] at target_jd given elements at epoch_jd."""
    a_km = a_au * AU_KM
    period_sec = 2 * np.pi * np.sqrt(a_km**3 / MU_SUN)
    n = 2 * np.pi / (period_sec / 86400)
    dt_days = target_jd - epoch_jd
    M = np.radians(ma_deg) + n * dt_days
    M = M % (2 * np.pi)
    return elements_to_state(a_au, e, i_deg, om_deg, w_deg, M)


def utc_to_jd(utc_str: str) -> float:
    """Convert UTC date string to Julian Date (approximate, good to ~1 second)."""
    from datetime import datetime
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00') if 'T' in utc_str
                                else utc_str + 'T12:00:00+00:00')
    # Julian Date formula
    y = dt.year
    m = dt.month
    d = dt.day + dt.hour / 24 + dt.minute / 1440 + dt.second / 86400
    if m <= 2:
        y -= 1
        m += 12
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5
