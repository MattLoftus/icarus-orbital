"""Ephemeris wrapper using SPICE for planet/body state vectors."""

import os
import threading
import numpy as np
import spiceypy as spice
from .constants import KERNEL_DIR, NAIF_IDS

_kernels_loaded = False
_spice_lock = threading.Lock()


def load_kernels():
    """Load SPICE kernels. Safe to call multiple times."""
    global _kernels_loaded
    if _kernels_loaded:
        return

    kernel_files = [
        os.path.join(KERNEL_DIR, 'naif0012.tls'),
        os.path.join(KERNEL_DIR, 'de440s.bsp'),
        os.path.join(KERNEL_DIR, 'pck00011.tpc'),
    ]
    for kf in kernel_files:
        if not os.path.exists(kf):
            raise FileNotFoundError(f"SPICE kernel not found: {kf}")
        spice.furnsh(kf)

    _kernels_loaded = True


def utc_to_et(utc_str: str) -> float:
    """Convert UTC string to SPICE ephemeris time (TDB seconds past J2000)."""
    load_kernels()
    with _spice_lock:
        return spice.str2et(utc_str)


def et_to_utc(et: float) -> str:
    """Convert SPICE ET to UTC ISO string."""
    load_kernels()
    with _spice_lock:
        return spice.et2utc(et, 'ISOC', 3)


def jd_to_et(jd: float) -> float:
    """Convert Julian Date to SPICE ET."""
    load_kernels()
    with _spice_lock:
        return spice.str2et(f'JD {jd} TDB')


def get_body_state(body: str, et: float, center: str = 'sun') -> np.ndarray:
    """Get body state vector [x, y, z, vx, vy, vz] in J2000 ecliptic frame.

    Args:
        body: Body name (e.g., 'earth', 'mars')
        et: SPICE ephemeris time
        center: Center body (default 'sun')

    Returns:
        ndarray of shape (6,) — [x, y, z] in km, [vx, vy, vz] in km/s
    """
    load_kernels()

    body_id = str(NAIF_IDS.get(body.lower(), body))
    center_id = str(NAIF_IDS.get(center.lower(), center))

    with _spice_lock:
        state, _ = spice.spkezr(body_id, et, 'ECLIPJ2000', 'NONE', center_id)
    return np.array(state)


def get_body_position(body: str, et: float, center: str = 'sun') -> np.ndarray:
    """Get body position [x, y, z] in km, J2000 ecliptic frame."""
    return get_body_state(body, et, center)[:3]


def get_body_velocity(body: str, et: float, center: str = 'sun') -> np.ndarray:
    """Get body velocity [vx, vy, vz] in km/s, J2000 ecliptic frame."""
    return get_body_state(body, et, center)[3:]


def get_states_over_range(body: str, et_start: float, et_end: float,
                          n_points: int = 360, center: str = 'sun') -> np.ndarray:
    """Get body states over a time range.

    Returns:
        ndarray of shape (n_points, 7) — [et, x, y, z, vx, vy, vz]
    """
    ets = np.linspace(et_start, et_end, n_points)
    result = np.zeros((n_points, 7))
    for i, et in enumerate(ets):
        state = get_body_state(body, et, center)
        result[i, 0] = et
        result[i, 1:] = state
    return result
