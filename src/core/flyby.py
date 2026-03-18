"""Gravity assist (flyby) computation using patched conics approximation.

In the patched conics model, a flyby is instantaneous: the spacecraft's
speed doesn't change relative to the flyby body, but the direction rotates,
producing a "free" delta-v in the heliocentric frame.
"""

import numpy as np
from typing import Tuple, Optional
from .constants import BODIES


def compute_flyby(v_in_helio: np.ndarray, v_body: np.ndarray,
                  mu_body: float, rp: float,
                  theta: float = 0.0) -> Tuple[np.ndarray, float, float]:
    """Compute the outbound heliocentric velocity after an unpowered flyby.

    Args:
        v_in_helio: Incoming spacecraft heliocentric velocity (km/s)
        v_body: Flyby body heliocentric velocity (km/s)
        mu_body: Flyby body gravitational parameter (km^3/s^2)
        rp: Flyby periapsis radius (km)
        theta: B-plane rotation angle (radians) — controls the flyby plane

    Returns:
        v_out_helio: Outbound heliocentric velocity (km/s)
        delta: Deflection angle (radians)
        dv_free: "Free" delta-v magnitude from gravity assist (km/s)
    """
    # Compute v-infinity (relative velocity to body)
    v_inf_in = v_in_helio - v_body
    v_inf_mag = np.linalg.norm(v_inf_in)

    if v_inf_mag < 1e-10:
        return v_in_helio.copy(), 0.0, 0.0

    # Deflection angle from hyperbolic flyby geometry
    # delta = 2 * arcsin(1 / (1 + rp * v_inf^2 / mu))
    e = 1.0 + rp * v_inf_mag**2 / mu_body  # hyperbolic eccentricity
    delta = 2.0 * np.arcsin(1.0 / e)

    # Build rotation: rotate v_inf_in by delta in the flyby plane
    # The flyby plane is defined by v_inf_in and a perpendicular direction
    # controlled by theta (the B-plane angle)
    v_inf_hat = v_inf_in / v_inf_mag

    # Find two perpendicular directions to v_inf_in
    # Use the ecliptic normal as reference unless colinear
    ref = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(v_inf_hat, ref)) > 0.99:
        ref = np.array([1.0, 0.0, 0.0])

    e1 = np.cross(v_inf_hat, ref)
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(v_inf_hat, e1)

    # Rotate v_inf_in by delta in the plane defined by theta
    # The perpendicular direction in the B-plane
    perp = np.cos(theta) * e1 + np.sin(theta) * e2

    # Rodrigues rotation of v_inf_in around perp by delta
    v_inf_out = (v_inf_in * np.cos(delta) +
                 np.cross(perp, v_inf_in) * np.sin(delta) +
                 perp * np.dot(perp, v_inf_in) * (1 - np.cos(delta)))

    v_out_helio = v_inf_out + v_body

    # Free delta-v
    dv_free = np.linalg.norm(v_out_helio - v_in_helio)

    return v_out_helio, delta, dv_free


def max_deflection(v_inf_mag: float, mu_body: float, rp_min: float) -> float:
    """Maximum deflection angle achievable at a given v-infinity and minimum periapsis.

    Args:
        v_inf_mag: V-infinity magnitude (km/s)
        mu_body: Body gravitational parameter (km^3/s^2)
        rp_min: Minimum periapsis radius (km)

    Returns:
        Maximum deflection angle in radians.
    """
    e = 1.0 + rp_min * v_inf_mag**2 / mu_body
    return 2.0 * np.arcsin(1.0 / e)


def max_free_dv(v_inf_mag: float, mu_body: float, rp_min: float) -> float:
    """Maximum free delta-v from a gravity assist.

    dv_free = 2 * v_inf * sin(delta/2)
    """
    delta = max_deflection(v_inf_mag, mu_body, rp_min)
    return 2.0 * v_inf_mag * np.sin(delta / 2.0)


def check_flyby_feasibility(v_inf_in: np.ndarray, v_inf_out: np.ndarray,
                            mu_body: float, rp_min: float
                            ) -> Tuple[bool, float, float]:
    """Check if a flyby is feasible (required deflection <= max deflection).

    Args:
        v_inf_in: Incoming v-infinity vector (km/s)
        v_inf_out: Required outgoing v-infinity vector (km/s)
        mu_body: Body gravitational parameter (km^3/s^2)
        rp_min: Minimum periapsis radius (km)

    Returns:
        feasible: True if the flyby is achievable
        rp_required: Periapsis radius needed for this deflection (km)
        delta_required: Required deflection angle (radians)
    """
    v_inf_mag_in = np.linalg.norm(v_inf_in)
    v_inf_mag_out = np.linalg.norm(v_inf_out)

    # For unpowered flyby, magnitudes must match
    if abs(v_inf_mag_in - v_inf_mag_out) / max(v_inf_mag_in, 1e-10) > 0.01:
        return False, np.inf, 0.0

    v_inf_mag = (v_inf_mag_in + v_inf_mag_out) / 2.0

    # Required deflection
    cos_delta = np.dot(v_inf_in, v_inf_out) / (v_inf_mag_in * v_inf_mag_out)
    cos_delta = np.clip(cos_delta, -1.0, 1.0)
    delta_required = np.arccos(cos_delta)

    # Periapsis needed for this deflection
    # delta = 2 * arcsin(1/e), e = 1 + rp*v_inf^2/mu
    # => e = 1/sin(delta/2)
    # => rp = mu * (e - 1) / v_inf^2
    sin_half = np.sin(delta_required / 2.0)
    if sin_half < 1e-10:
        return True, np.inf, 0.0  # no deflection needed

    e = 1.0 / sin_half
    rp_required = mu_body * (e - 1.0) / v_inf_mag**2

    feasible = rp_required >= rp_min
    return feasible, rp_required, delta_required
