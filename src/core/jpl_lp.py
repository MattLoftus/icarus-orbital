"""JPL Low-Precision Analytical Ephemeris for GTOP benchmark compatibility.

Implements the "Approximate Positions of the Planets" by E.M. Standish (1992),
Table 1 (valid 1800–2050 AD). This is the exact ephemeris used by pykep/GTOP.

Reference: https://ssd.jpl.nasa.gov/planets/approx_pos.html

Positions are in the J2000 ecliptic frame (same as GTOP expects).
Units: km and km/s (converted from SI internally).
"""

import numpy as np
from typing import Tuple

# GTOP constants (pykep v2 — exact values for benchmark reproduction)
GTOP_AU_M = 149597870691.0          # meters
GTOP_AU_KM = GTOP_AU_M / 1000.0    # km
GTOP_MU_SUN_M3S2 = 1.32712440018e20  # m^3/s^2
GTOP_MU_SUN = GTOP_MU_SUN_M3S2 / 1e9  # km^3/s^2

DEG2RAD = np.pi / 180.0

# Table 1 coefficients: [a0, a_dot, e0, e_dot, I0, I_dot, L0, L_dot, w0, w_dot, O0, O_dot]
# a in AU, a_dot in AU/cy, angles in degrees, rates in deg/cy
_ELEMENTS = {
    'mercury': [
        0.38709927, 0.00000037,
        0.20563593, 0.00001906,
        7.00497902, -0.00594749,
        252.25032350, 149472.67411175,
        77.45779628, 0.16047689,
        48.33076593, -0.12534081,
    ],
    'venus': [
        0.72333566, 0.00000390,
        0.00677672, -0.00004107,
        3.39467605, -0.00078890,
        181.97909950, 58517.81538729,
        131.60246718, 0.00268329,
        76.67984255, -0.27769418,
    ],
    'earth': [
        1.00000261, 0.00000562,
        0.01671123, -0.00004392,
        -0.00001531, -0.01294668,
        100.46457166, 35999.37244981,
        102.93768193, 0.32327364,
        0.0, 0.0,
    ],
    'mars': [
        1.52371034, 0.00001847,
        0.09339410, 0.00007882,
        1.84969142, -0.00813131,
        -4.55343205, 19140.30268499,
        -23.94362959, 0.44441088,
        49.55953891, -0.29257343,
    ],
    'jupiter': [
        5.20288700, -0.00011607,
        0.04838624, -0.00013253,
        1.30439695, -0.00183714,
        34.39644051, 3034.74612775,
        14.72847983, 0.21252668,
        100.47390909, 0.20469106,
    ],
    'saturn': [
        9.53667594, -0.00125060,
        0.05386179, -0.00050991,
        2.48599187, 0.00193609,
        49.95424423, 1222.49362201,
        92.59887831, -0.41897216,
        113.66242448, -0.28867794,
    ],
    'uranus': [
        19.18916464, -0.00196176,
        0.04725744, -0.00004397,
        0.77263783, -0.00242939,
        313.23810451, 428.48202785,
        170.95427630, 0.40805281,
        74.01692503, 0.04240589,
    ],
    'neptune': [
        30.06992276, 0.00026291,
        0.00859048, 0.00005105,
        1.77004347, 0.00035372,
        -55.12002969, 218.45945325,
        44.96476227, -0.32241464,
        131.78422574, -0.00508664,
    ],
}

# GTOP body parameters: mu (km^3/s^2), radius (km), safe_radius_factor
_BODY_PARAMS = {
    'mercury': {'mu': 22032.0, 'radius': 2440.0, 'safe_factor': 1.1},
    'venus':   {'mu': 324859.0, 'radius': 6052.0, 'safe_factor': 1.1},
    'earth':   {'mu': 398600.4418, 'radius': 6378.0, 'safe_factor': 1.1},
    'mars':    {'mu': 42828.0, 'radius': 3397.0, 'safe_factor': 1.1},
    'jupiter': {'mu': 126686534.0, 'radius': 71492.0, 'safe_factor': 9.0},
    'saturn':  {'mu': 37931187.0, 'radius': 60330.0, 'safe_factor': 1.1},
    'uranus':  {'mu': 5793939.0, 'radius': 25559.0, 'safe_factor': 1.1},
    'neptune': {'mu': 6836529.0, 'radius': 24766.0, 'safe_factor': 1.1},
}


def _solve_kepler(M: float, e: float, tol: float = 1e-16) -> float:
    """Solve Kepler's equation M = E - e*sin(E) for eccentric anomaly E.

    Uses Newton-Raphson with the standard initial guess.
    Matches pykep's implementation for GTOP compatibility.
    """
    E = M + e * np.sin(M)  # initial guess
    for _ in range(50):
        dE = (M - E + e * np.sin(E)) / (1.0 - e * np.cos(E))
        E += dE
        if abs(dE) < tol:
            break
    return E


def jpl_lp_state(body: str, mjd2000: float) -> np.ndarray:
    """Compute body state [x,y,z,vx,vy,vz] using JPL low-precision ephemeris.

    Args:
        body: Planet name (lowercase)
        mjd2000: MJD2000 epoch (days since 2000-01-01 00:00 UTC)

    Returns:
        State vector [x,y,z] in km, [vx,vy,vz] in km/s, ecliptic J2000.
    """
    if body.lower() not in _ELEMENTS:
        raise ValueError(f"Unknown body: {body}")

    coeffs = _ELEMENTS[body.lower()]

    # Julian centuries from J2000.0
    T = (mjd2000 - 0.5) / 36525.0

    # Compute current elements (linear in T)
    a_au = coeffs[0] + coeffs[1] * T       # semi-major axis (AU)
    e = coeffs[2] + coeffs[3] * T           # eccentricity
    I_deg = coeffs[4] + coeffs[5] * T       # inclination (deg)
    L_deg = coeffs[6] + coeffs[7] * T       # mean longitude (deg)
    varpi_deg = coeffs[8] + coeffs[9] * T   # longitude of perihelion (deg)
    Omega_deg = coeffs[10] + coeffs[11] * T  # longitude of ascending node (deg)

    # Derived Keplerian elements
    omega_deg = varpi_deg - Omega_deg        # argument of perihelion (deg)
    M_deg = L_deg - varpi_deg                # mean anomaly (deg)

    # Convert to radians
    i = I_deg * DEG2RAD
    Omega = Omega_deg * DEG2RAD
    omega = omega_deg * DEG2RAD
    M = (M_deg * DEG2RAD) % (2.0 * np.pi)

    # Solve Kepler's equation for eccentric anomaly
    E = _solve_kepler(M, e)

    # Convert to Cartesian in perifocal frame
    a_km = a_au * GTOP_AU_KM
    mu = GTOP_MU_SUN

    cos_E = np.cos(E)
    sin_E = np.sin(E)
    sqrt_1me2 = np.sqrt(1.0 - e * e)
    denom = 1.0 - e * cos_E

    # Position in perifocal frame
    x_peri = a_km * (cos_E - e)
    y_peri = a_km * sqrt_1me2 * sin_E

    # Velocity in perifocal frame
    n = np.sqrt(mu / (a_km ** 3))  # mean motion (rad/s)
    vx_peri = -a_km * n * sin_E / denom
    vy_peri = a_km * sqrt_1me2 * n * cos_E / denom

    # Rotation matrix: perifocal → ecliptic J2000
    cos_O = np.cos(Omega)
    sin_O = np.sin(Omega)
    cos_w = np.cos(omega)
    sin_w = np.sin(omega)
    cos_i = np.cos(i)
    sin_i = np.sin(i)

    R00 = cos_O * cos_w - sin_O * sin_w * cos_i
    R01 = -cos_O * sin_w - sin_O * cos_w * cos_i
    R10 = sin_O * cos_w + cos_O * sin_w * cos_i
    R11 = -sin_O * sin_w + cos_O * cos_w * cos_i
    R20 = sin_w * sin_i
    R21 = cos_w * sin_i

    # Apply rotation
    x = R00 * x_peri + R01 * y_peri
    y = R10 * x_peri + R11 * y_peri
    z = R20 * x_peri + R21 * y_peri

    vx = R00 * vx_peri + R01 * vy_peri
    vy = R10 * vx_peri + R11 * vy_peri
    vz = R20 * vx_peri + R21 * vy_peri

    return np.array([x, y, z, vx, vy, vz])


def get_gtop_body_params(body: str) -> dict:
    """Get GTOP-specific body parameters (mu, radius, safe_radius)."""
    params = _BODY_PARAMS[body.lower()]
    return {
        'mu': params['mu'],
        'radius': params['radius'],
        'rp_min': params['radius'] * params['safe_factor'],
    }
