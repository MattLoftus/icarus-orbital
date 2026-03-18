"""Keplerian orbit propagation for trajectory visualization.

Given initial state (position + velocity), propagate the orbit forward in time
using the two-body Kepler problem (analytical, no numerical integration needed).
"""

import numpy as np
from typing import List, Tuple
from .constants import MU_SUN


def state_to_elements(r: np.ndarray, v: np.ndarray, mu: float = MU_SUN) -> dict:
    """Convert state vector to Keplerian orbital elements.

    Returns:
        Dict with: a (km), e, i (rad), omega (rad), w (rad), nu (rad),
                   h (angular momentum vector), energy
    """
    r_mag = np.linalg.norm(r)
    v_mag = np.linalg.norm(v)

    # Angular momentum
    h = np.cross(r, v)
    h_mag = np.linalg.norm(h)

    # Node vector
    k = np.array([0, 0, 1])
    n = np.cross(k, h)
    n_mag = np.linalg.norm(n)

    # Eccentricity vector
    e_vec = ((v_mag**2 - mu / r_mag) * r - np.dot(r, v) * v) / mu
    e = np.linalg.norm(e_vec)

    # Specific energy
    energy = v_mag**2 / 2 - mu / r_mag

    # Semi-major axis
    if abs(1 - e) > 1e-10:
        a = -mu / (2 * energy)
    else:
        a = np.inf  # parabolic

    # Inclination
    i = np.arccos(np.clip(h[2] / h_mag, -1, 1))

    # RAAN (longitude of ascending node)
    if n_mag > 1e-10:
        omega = np.arccos(np.clip(n[0] / n_mag, -1, 1))
        if n[1] < 0:
            omega = 2 * np.pi - omega
    else:
        omega = 0.0

    # Argument of periapsis
    if n_mag > 1e-10 and e > 1e-10:
        w = np.arccos(np.clip(np.dot(n, e_vec) / (n_mag * e), -1, 1))
        if e_vec[2] < 0:
            w = 2 * np.pi - w
    else:
        w = 0.0

    # True anomaly
    if e > 1e-10:
        nu = np.arccos(np.clip(np.dot(e_vec, r) / (e * r_mag), -1, 1))
        if np.dot(r, v) < 0:
            nu = 2 * np.pi - nu
    else:
        nu = 0.0

    return {
        'a': a, 'e': e, 'i': i, 'omega': omega, 'w': w, 'nu': nu,
        'h': h, 'h_mag': h_mag, 'energy': energy,
    }


def propagate_kepler(r0: np.ndarray, v0: np.ndarray, dt: float,
                     mu: float = MU_SUN) -> Tuple[np.ndarray, np.ndarray]:
    """Propagate state forward by dt seconds using universal variable formulation.

    This handles elliptic, parabolic, and hyperbolic orbits.

    Args:
        r0: Initial position (km)
        v0: Initial velocity (km/s)
        dt: Time step (seconds)
        mu: Gravitational parameter (km^3/s^2)

    Returns:
        r1, v1: Position and velocity after dt seconds
    """
    from .lambert import _stumpff_c2, _stumpff_c3

    r0_mag = np.linalg.norm(r0)
    v0_mag = np.linalg.norm(v0)

    # Specific energy → semi-major axis
    energy = v0_mag**2 / 2 - mu / r0_mag
    alpha = -2 * energy / mu  # 1/a

    # Radial velocity component
    vr0 = np.dot(r0, v0) / r0_mag

    # Initial guess for universal variable chi
    if alpha > 1e-10:  # elliptic
        chi = np.sqrt(mu) * dt * alpha
    elif alpha < -1e-10:  # hyperbolic
        a = 1 / alpha
        chi = np.sign(dt) * np.sqrt(-a) * np.log(
            (-2 * mu * alpha * dt) /
            (np.dot(r0, v0) + np.sign(dt) * np.sqrt(-mu * a) * (1 - r0_mag * alpha))
        )
    else:  # parabolic
        h = np.cross(r0, v0)
        p = np.linalg.norm(h)**2 / mu
        s = 0.5 * np.arctan(1 / (3 * np.sqrt(mu / p**3) * dt))
        w = np.arctan(np.tan(s)**(1/3))
        chi = np.sqrt(p) * 2 / np.tan(2 * w)

    # Newton-Raphson iteration on universal Kepler's equation
    for _ in range(50):
        psi = chi**2 * alpha
        c2 = _stumpff_c2(psi)
        c3 = _stumpff_c3(psi)

        r = chi**2 * c2 + vr0 / np.sqrt(mu) * chi * (1 - psi * c3) + r0_mag * (1 - psi * c2)

        # F(chi) = 0
        f_chi = (r0_mag * vr0 / np.sqrt(mu)) * chi**2 * c2 + \
                (1 - r0_mag * alpha) * chi**3 * c3 + r0_mag * chi - np.sqrt(mu) * dt

        f_prime = chi**2 * c2 + vr0 / np.sqrt(mu) * chi * (1 - psi * c3) + r0_mag * (1 - psi * c2)

        if abs(f_prime) < 1e-14:
            break

        delta = f_chi / f_prime
        chi = chi - delta

        if abs(delta) < 1e-10:
            break

    # Compute Lagrange coefficients
    psi = chi**2 * alpha
    c2 = _stumpff_c2(psi)
    c3 = _stumpff_c3(psi)

    f = 1 - chi**2 / r0_mag * c2
    g = dt - chi**3 / np.sqrt(mu) * c3

    r1 = f * r0 + g * v0
    r1_mag = np.linalg.norm(r1)

    f_dot = np.sqrt(mu) / (r1_mag * r0_mag) * chi * (psi * c3 - 1)
    g_dot = 1 - chi**2 / r1_mag * c2

    v1 = f_dot * r0 + g_dot * v0

    return r1, v1


def generate_trajectory_points(r0: np.ndarray, v0: np.ndarray,
                               total_time: float, n_points: int = 100,
                               mu: float = MU_SUN) -> List[List[float]]:
    """Generate trajectory position points for visualization.

    Args:
        r0: Initial position (km)
        v0: Initial velocity (km/s)
        total_time: Total propagation time (seconds)
        n_points: Number of output points
        mu: Gravitational parameter

    Returns:
        List of [x, y, z] positions in km
    """
    positions = [r0.tolist()]
    dt = total_time / (n_points - 1)

    r, v = r0.copy(), v0.copy()
    for i in range(1, n_points):
        r, v = propagate_kepler(r, v, dt, mu)
        positions.append(r.tolist())

    return positions
