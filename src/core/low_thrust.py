"""Low-thrust trajectory optimization using the Sims-Flanagan method.

Discretizes a trajectory into N segments. Each segment has an impulsive
delta-v at its midpoint, bounded by the spacecraft's thrust capability.
Forward and backward propagation meet at a match point; the NLP enforces
continuity there.

References:
    Sims & Flanagan (1999), "Preliminary Design of Low-Thrust Interplanetary Missions"
    Englander & Conway (2017), "An Automated Solution of the Low-Thrust Interplanetary Trajectory Problem"
"""

import numpy as np
from scipy.optimize import minimize
from typing import Dict, List, Optional, Tuple
from .propagate import propagate_kepler
from .lambert import solve_lambert
from .ephemeris import get_body_state, utc_to_et, et_to_utc
from .constants import MU_SUN


G0 = 9.80665e-3  # gravitational acceleration, km/s^2


class Spacecraft:
    """Spacecraft parameters for low-thrust propulsion."""

    def __init__(self, m0: float = 1000.0, m_dry: float = 500.0,
                 thrust_n: float = 0.1, isp: float = 3000.0):
        """
        Args:
            m0: Initial wet mass (kg)
            m_dry: Dry mass — structure + payload (kg)
            thrust_n: Maximum thrust (Newtons)
            isp: Specific impulse (seconds)
        """
        self.m0 = m0
        self.m_dry = m_dry
        self.thrust = thrust_n * 1e-3  # Convert N to kN (km*kg/s^2)
        self.isp = isp
        self.ve = isp * G0  # Exhaust velocity (km/s)

    def max_dv_per_segment(self, dt: float, mass: float) -> float:
        """Maximum delta-v achievable in one segment at given mass.

        Args:
            dt: Segment duration (seconds)
            mass: Spacecraft mass (kg)

        Returns:
            Maximum delta-v (km/s)
        """
        return self.thrust * dt / mass


class SimsFlanagan:
    """Sims-Flanagan low-thrust trajectory optimizer."""

    def __init__(self, departure_body: str, arrival_body: str,
                 departure_date: str, arrival_date: str,
                 spacecraft: Spacecraft, n_segments: int = 20):
        """
        Args:
            departure_body: e.g., 'earth'
            arrival_body: e.g., 'mars'
            departure_date: UTC string
            arrival_date: UTC string
            spacecraft: Spacecraft parameters
            n_segments: Number of trajectory segments
        """
        self.dep_body = departure_body
        self.arr_body = arrival_body
        self.sc = spacecraft
        self.n_seg = n_segments
        self.n_fwd = n_segments // 2
        self.n_bwd = n_segments - self.n_fwd

        # Compute times
        self.et_dep = utc_to_et(departure_date)
        self.et_arr = utc_to_et(arrival_date)
        self.tof = self.et_arr - self.et_dep
        self.dt = self.tof / n_segments

        # Get body states
        self.dep_state = get_body_state(departure_body, self.et_dep)
        self.arr_state = get_body_state(arrival_body, self.et_arr)
        self.r_dep = self.dep_state[:3]
        self.v_dep_body = self.dep_state[3:]
        self.r_arr = self.arr_state[:3]
        self.v_arr_body = self.arr_state[3:]

        # Lambert solution for initial guess
        self.v1_lambert, self.v2_lambert = solve_lambert(
            self.r_dep, self.r_arr, self.tof, MU_SUN
        )

    @property
    def n_vars(self) -> int:
        """Number of decision variables: 3*N throttles + 3 v_dep + 3 v_arr."""
        return 3 * self.n_seg + 6

    def _unpack(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Unpack decision vector into throttles, v_dep, v_arr."""
        throttles = x[:3 * self.n_seg].reshape(self.n_seg, 3)
        v_dep = x[3 * self.n_seg: 3 * self.n_seg + 3]
        v_arr = x[3 * self.n_seg + 3: 3 * self.n_seg + 6]
        return throttles, v_dep, v_arr

    def _propagate_forward(self, v_dep: np.ndarray, throttles: np.ndarray
                           ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Propagate forward half from departure to match point.

        Returns (r, v, mass) at the match point.
        """
        r = self.r_dep.copy()
        v = v_dep.copy()
        m = self.sc.m0

        for k in range(self.n_fwd):
            # Coast dt/2
            r, v = propagate_kepler(r, v, self.dt / 2, MU_SUN)

            # Apply impulse at midpoint
            dv_max = self.sc.max_dv_per_segment(self.dt, m)
            dv = throttles[k] * dv_max
            v = v + dv

            # Update mass (linear approximation)
            throttle_mag = np.linalg.norm(throttles[k])
            dm = self.sc.thrust * self.dt * throttle_mag / self.sc.ve
            m = max(m - dm, self.sc.m_dry)

            # Coast dt/2
            r, v = propagate_kepler(r, v, self.dt / 2, MU_SUN)

        return r, v, m

    def _propagate_backward(self, v_arr: np.ndarray, throttles: np.ndarray,
                            m_arr: float) -> Tuple[np.ndarray, np.ndarray, float]:
        """Propagate backward half from arrival to match point.

        Returns (r, v, mass) at the match point.
        """
        r = self.r_arr.copy()
        v = v_arr.copy()
        m = m_arr

        for k in range(self.n_seg - 1, self.n_fwd - 1, -1):
            # Coast backward dt/2
            r, v = propagate_kepler(r, v, -self.dt / 2, MU_SUN)

            # Add mass back (going backward)
            throttle_mag = np.linalg.norm(throttles[k])
            dm = self.sc.thrust * self.dt * throttle_mag / self.sc.ve
            m = m + dm

            # Apply impulse (subtract — backward propagation)
            dv_max = self.sc.max_dv_per_segment(self.dt, m)
            dv = throttles[k] * dv_max
            v = v - dv

            # Coast backward dt/2
            r, v = propagate_kepler(r, v, -self.dt / 2, MU_SUN)

        return r, v, m

    def _objective(self, x: np.ndarray) -> float:
        """Minimize total propellant proxy: throttle usage + departure/arrival v-infinity.

        A pure low-thrust mission has near-zero v-infinity at both ends —
        the thruster does all the work. We penalize v-infinity heavily to
        force the optimizer to use thrust segments instead of ballistic coasting.
        """
        throttles, v_dep, v_arr = self._unpack(x)

        # Throttle cost (proxy for propellant consumed by thruster)
        throttle_cost = sum(np.dot(t, t) for t in throttles)

        # V-infinity penalties (force low-thrust solution, not ballistic)
        v_inf_dep = np.linalg.norm(v_dep - self.v_dep_body)
        v_inf_arr = np.linalg.norm(v_arr - self.v_arr_body)

        # Weight: penalize v-infinity more than throttle to push toward pure low-thrust
        # A 1 km/s v-infinity "costs" about the same as using all 20 segments at full throttle
        vinf_weight = self.n_seg * 0.5
        return throttle_cost + vinf_weight * (v_inf_dep**2 + v_inf_arr**2)

    def _match_constraints(self, x: np.ndarray) -> np.ndarray:
        """Return 6-vector of match point defects (must equal zero).

        Position and velocity continuity at match point.
        Mass continuity is handled implicitly via the objective.
        """
        throttles, v_dep, v_arr = self._unpack(x)

        try:
            r_fwd, v_fwd, m_fwd = self._propagate_forward(v_dep, throttles)

            # Estimate arrival mass from forward prop total consumption
            total_dm = sum(
                self.sc.thrust * self.dt * np.linalg.norm(throttles[k]) / self.sc.ve
                for k in range(self.n_seg)
            )
            m_arr = max(self.sc.m0 - total_dm, self.sc.m_dry)

            r_bwd, v_bwd, m_bwd = self._propagate_backward(v_arr, throttles, m_arr)
        except Exception:
            return np.ones(6) * 1e10

        # Normalize defects for better conditioning
        au = 1.496e8
        defect_r = (r_fwd - r_bwd) / au
        defect_v = (v_fwd - v_bwd) / 30.0  # ~Earth orbital velocity

        return np.concatenate([defect_r, defect_v])

    def _throttle_constraints(self, x: np.ndarray) -> np.ndarray:
        """Return N values, each must be >= 0 for ||u_k||^2 <= 1."""
        throttles = x[:3 * self.n_seg].reshape(self.n_seg, 3)
        return np.array([1.0 - np.dot(t, t) for t in throttles])

    def optimize(self, max_iter: int = 500) -> Dict:
        """Run the Sims-Flanagan optimization.

        Returns:
            Dict with trajectory solution details.
        """
        # Initial guess: Lambert velocities, zero throttle
        x0 = np.zeros(self.n_vars)
        x0[3 * self.n_seg: 3 * self.n_seg + 3] = self.v1_lambert
        x0[3 * self.n_seg + 3: 3 * self.n_seg + 6] = self.v2_lambert

        # Bounds: throttle components in [-1, 1], velocities free
        bounds = [(-1, 1)] * (3 * self.n_seg) + [(None, None)] * 6

        result = minimize(
            self._objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=[
                {'type': 'eq', 'fun': self._match_constraints},
                {'type': 'ineq', 'fun': self._throttle_constraints},
            ],
            options={'maxiter': max_iter, 'ftol': 1e-8, 'disp': False},
        )

        return self._build_solution(result)

    def _build_solution(self, opt_result) -> Dict:
        """Build solution dict from optimization result."""
        throttles, v_dep, v_arr = self._unpack(opt_result.x)

        # Reconstruct full trajectory by forward propagation
        positions = []
        r = self.r_dep.copy()
        v = v_dep.copy()
        m = self.sc.m0
        thrust_vectors = []
        masses = [m]

        for k in range(self.n_seg):
            # Coast dt/2, record position
            r, v = propagate_kepler(r, v, self.dt / 2, MU_SUN)
            positions.append(r.tolist())

            # Apply impulse
            dv_max = self.sc.max_dv_per_segment(self.dt, m)
            dv = throttles[k] * dv_max
            v = v + dv

            # Record thrust
            thrust_vectors.append({
                'throttle': throttles[k].tolist(),
                'dv': dv.tolist(),
                'dv_mag': float(np.linalg.norm(dv)),
                'throttle_mag': float(np.linalg.norm(throttles[k])),
            })

            # Mass update
            throttle_mag = np.linalg.norm(throttles[k])
            dm = self.sc.thrust * self.dt * throttle_mag / self.sc.ve
            m = max(m - dm, self.sc.m_dry)
            masses.append(m)

            # Coast dt/2
            r, v = propagate_kepler(r, v, self.dt / 2, MU_SUN)
            positions.append(r.tolist())

        # Total delta-v and propellant
        total_dv = sum(tv['dv_mag'] for tv in thrust_vectors)
        propellant_mass = self.sc.m0 - m
        dv_departure = float(np.linalg.norm(v_dep - self.v_dep_body))
        dv_arrival = float(np.linalg.norm(v_arr - self.v_arr_body))

        return {
            'departure_body': self.dep_body,
            'arrival_body': self.arr_body,
            'departure_utc': et_to_utc(self.et_dep),
            'arrival_utc': et_to_utc(self.et_arr),
            'tof_days': self.tof / 86400,
            'n_segments': self.n_seg,
            'propulsion': {
                'type': 'low-thrust',
                'thrust_n': self.sc.thrust * 1e3,
                'isp_s': self.sc.isp,
                'm0_kg': self.sc.m0,
                'm_dry_kg': self.sc.m_dry,
                'm_final_kg': float(m),
                'propellant_kg': float(propellant_mass),
            },
            'dv_total': float(total_dv),
            'dv_departure_vinf': dv_departure,
            'dv_arrival_vinf': dv_arrival,
            'c3_launch': dv_departure**2,
            'trajectory_positions': positions,
            'thrust_profile': thrust_vectors,
            'mass_profile': masses,
            'optimizer': {
                'success': bool(opt_result.success),
                'message': str(opt_result.message),
                'n_iterations': int(opt_result.nit),
                'objective': float(opt_result.fun),
            },
        }


def optimize_low_thrust(departure_body: str, arrival_body: str,
                        departure_date: str, arrival_date: str,
                        thrust_n: float = 0.1, isp: float = 3000.0,
                        m0: float = 1000.0, m_dry: float = 500.0,
                        n_segments: int = 20, max_iter: int = 500) -> Dict:
    """Convenience function for low-thrust trajectory optimization.

    Args:
        departure_body: e.g., 'earth'
        arrival_body: e.g., 'mars'
        departure_date: UTC string
        arrival_date: UTC string
        thrust_n: Maximum thrust in Newtons
        isp: Specific impulse in seconds
        m0: Initial wet mass in kg
        m_dry: Dry mass in kg
        n_segments: Number of trajectory segments
        max_iter: Maximum optimizer iterations

    Returns:
        Dict with solution details
    """
    sc = Spacecraft(m0=m0, m_dry=m_dry, thrust_n=thrust_n, isp=isp)
    sf = SimsFlanagan(departure_body, arrival_body,
                      departure_date, arrival_date, sc, n_segments)
    return sf.optimize(max_iter=max_iter)
