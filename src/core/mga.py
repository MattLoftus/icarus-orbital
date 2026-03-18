"""Multiple Gravity Assist with 1 Deep Space Maneuver (MGA-1DSM) trajectory optimizer.

Optimizes interplanetary trajectories with gravity assists using
scipy.optimize.differential_evolution as the global optimizer.

The MGA-1DSM model allows one impulsive deep-space maneuver per leg,
making it more flexible than pure MGA (which only allows maneuvers at flyby bodies).

Decision variables per trajectory:
    - t0: departure epoch (ET seconds)
    - v_inf_mag: departure v-infinity magnitude (km/s)
    - v_inf_u, v_inf_v: departure v-infinity direction (unit sphere coords)
    - For each leg i:
        - tof_i: time of flight for leg i (seconds)
"""

import numpy as np
from scipy.optimize import differential_evolution, OptimizeResult
from typing import List, Tuple, Dict, Optional
from .lambert import solve_lambert
from .flyby import compute_flyby, check_flyby_feasibility, max_deflection
from .ephemeris import get_body_state, utc_to_et
from .constants import MU_SUN, BODIES


class MGATrajectory:
    """Represents an MGA trajectory problem definition."""

    def __init__(self, sequence: List[str],
                 dep_window: Tuple[str, str],
                 tof_bounds: List[Tuple[float, float]],
                 v_inf_max: float = 6.0,
                 n_restarts: int = None):
        """
        Args:
            sequence: List of body names, e.g., ['earth', 'venus', 'mars']
            dep_window: (start_utc, end_utc) for departure
            tof_bounds: List of (min_days, max_days) for each leg
            v_inf_max: Maximum departure v-infinity (km/s)
            n_restarts: Number of optimizer restarts with different seeds.
                        Defaults to 1 for direct transfers, 6 for multi-flyby.
        """
        self.sequence = [s.lower() for s in sequence]
        self.n_legs = len(sequence) - 1

        if len(tof_bounds) != self.n_legs:
            raise ValueError(f"Need {self.n_legs} TOF bounds for {self.n_legs} legs, got {len(tof_bounds)}")

        self.dep_window_et = (utc_to_et(dep_window[0]), utc_to_et(dep_window[1]))
        self.tof_bounds = tof_bounds
        self.v_inf_max = v_inf_max

        # Multi-flyby missions get more restarts by default
        if n_restarts is not None:
            self.n_restarts = n_restarts
        else:
            self.n_restarts = 1 if self.n_legs <= 1 else 6

        # Get body properties
        self.body_props = []
        for name in self.sequence:
            if name not in BODIES:
                raise ValueError(f"Unknown body: {name}")
            self.body_props.append(BODIES[name])

    @property
    def n_vars(self) -> int:
        """Number of decision variables."""
        # t0 + v_inf (mag, u, v) + per leg (tof) = 4 + n_legs
        return 4 + self.n_legs

    def get_bounds(self) -> List[Tuple[float, float]]:
        """Get bounds for all decision variables."""
        bounds = [
            (self.dep_window_et[0], self.dep_window_et[1]),  # t0 (ET)
            (0.1, self.v_inf_max),  # v_inf magnitude
            (0.0, 1.0),  # u (for direction)
            (0.0, 1.0),  # v (for direction)
        ]
        for tof_min, tof_max in self.tof_bounds:
            bounds.append((tof_min * 86400, tof_max * 86400))  # convert days to seconds
        return bounds

    def decode(self, x: np.ndarray) -> Dict:
        """Decode decision variables into trajectory parameters."""
        t0 = x[0]
        v_inf_mag = x[1]
        u, v = x[2], x[3]

        # Convert u, v to direction on unit sphere
        theta = 2 * np.pi * u
        phi = np.arccos(2 * v - 1)
        v_inf_dir = np.array([
            np.sin(phi) * np.cos(theta),
            np.sin(phi) * np.sin(theta),
            np.cos(phi),
        ])

        tofs = x[4:]  # already in seconds

        return {
            't0': t0,
            'v_inf_mag': v_inf_mag,
            'v_inf_dir': v_inf_dir,
            'tofs': tofs,
        }

    def _compute_flyby_dv(self, v_inf_in: np.ndarray, v_inf_out: np.ndarray,
                           mu_body: float, rp_min: float) -> float:
        """Compute the delta-v cost of a flyby, including powered assist if needed.

        For an unpowered gravity assist, the v-infinity magnitude is conserved
        and only the direction changes. If the required deflection exceeds what
        the body can provide at minimum periapsis, a powered flyby (periapsis
        maneuver) is needed.

        This returns a smooth cost that the optimizer can follow:
        - 0 for a perfect unpowered flyby
        - Small for near-feasible (slight speed mismatch or excess deflection)
        - Large for wildly infeasible geometries

        Returns:
            Total flyby delta-v cost (km/s)
        """
        v_inf_in_mag = np.linalg.norm(v_inf_in)
        v_inf_out_mag = np.linalg.norm(v_inf_out)

        if v_inf_in_mag < 1e-10 or v_inf_out_mag < 1e-10:
            return abs(v_inf_out_mag - v_inf_in_mag)

        # Cost 1: Speed mismatch — for unpowered flyby, |v_inf| must be conserved.
        # This requires a tangential burn at periapsis.
        speed_mismatch = abs(v_inf_out_mag - v_inf_in_mag)

        # Cost 2: Deflection feasibility
        # Required deflection angle
        cos_delta = np.dot(v_inf_in, v_inf_out) / (v_inf_in_mag * v_inf_out_mag)
        cos_delta = np.clip(cos_delta, -1.0, 1.0)
        delta_required = np.arccos(cos_delta)

        # Maximum deflection achievable at minimum periapsis
        v_inf_avg = (v_inf_in_mag + v_inf_out_mag) / 2.0
        delta_max = max_deflection(v_inf_avg, mu_body, rp_min)

        deflection_cost = 0.0
        if delta_required > delta_max and delta_max > 1e-10:
            # Proportional penalty based on how much extra deflection is needed.
            # Scales as v_inf * excess_angle, which has units of km/s (like dv).
            excess_angle = delta_required - delta_max
            deflection_cost = v_inf_avg * excess_angle

        return speed_mismatch + deflection_cost

    def evaluate(self, x: np.ndarray) -> float:
        """Evaluate total delta-v for a given set of decision variables.

        Returns total delta-v (km/s). Returns a large penalty value for infeasible trajectories.
        """
        PENALTY = 1e6

        try:
            params = self.decode(x)
        except Exception:
            return PENALTY

        t0 = params['t0']
        v_inf_mag = params['v_inf_mag']
        v_inf_dir = params['v_inf_dir']
        tofs = params['tofs']

        total_dv = 0.0

        # Departure
        dep_state = get_body_state(self.sequence[0], t0)
        v_dep_body = dep_state[3:]
        v_spacecraft = v_dep_body + v_inf_mag * v_inf_dir

        # Total departure v-infinity contributes to C3 / launch cost
        total_dv += v_inf_mag

        current_time = t0
        current_v = v_spacecraft

        for leg in range(self.n_legs):
            tof = tofs[leg]
            arrival_time = current_time + tof

            # Get positions
            r1 = get_body_state(self.sequence[leg], current_time)[:3]
            r2_state = get_body_state(self.sequence[leg + 1], arrival_time)
            r2 = r2_state[:3]
            v2_body = r2_state[3:]

            # Solve Lambert for this leg
            try:
                v1_lambert, v2_lambert = solve_lambert(r1, r2, tof, MU_SUN)
            except (ValueError, RuntimeError):
                return PENALTY

            if leg == 0:
                # First leg: DSM is difference between actual departure velocity
                # and the Lambert solution's required departure velocity
                dsm_dv = np.linalg.norm(v1_lambert - current_v)
                total_dv += dsm_dv
            else:
                # Intermediate legs: flyby at this body
                flyby_state = get_body_state(self.sequence[leg], current_time)
                v_flyby_body = flyby_state[3:]

                v_inf_in = current_v - v_flyby_body
                v_inf_out = v1_lambert - v_flyby_body

                mu_flyby = self.body_props[leg]['mu']
                rp_min = self.body_props[leg].get('rp_min',
                         self.body_props[leg]['radius'] * 1.05)

                flyby_dv = self._compute_flyby_dv(v_inf_in, v_inf_out,
                                                   mu_flyby, rp_min)
                total_dv += flyby_dv

            # Update for next leg
            current_time = arrival_time
            current_v = v2_lambert

        # Final arrival delta-v (to match target body velocity)
        v_inf_arr = np.linalg.norm(current_v - v2_body)
        total_dv += v_inf_arr

        return total_dv

    def optimize(self, max_iter: int = 1000, pop_size: int = 50,
                 tol: float = 1e-3, seed: int = 42,
                 callback=None) -> Dict:
        """Run differential evolution to find optimal trajectory.

        For multi-flyby missions, runs multiple restarts with different seeds
        and returns the best result. Population size and iterations are also
        scaled up for multi-flyby to better explore the larger search space.

        Args:
            max_iter: Maximum iterations
            pop_size: Population size multiplier
            tol: Convergence tolerance
            seed: Random seed (base seed; restarts use seed+i)
            callback: Optional callback(xk, convergence) called each iteration

        Returns:
            Dict with optimal trajectory parameters and delta-v breakdown
        """
        bounds = self.get_bounds()

        # Scale up optimizer effort for multi-flyby missions
        effective_pop = pop_size
        effective_iter = max_iter
        if self.n_legs > 1:
            effective_pop = max(pop_size, int(pop_size * 1.5))
            effective_iter = max(max_iter, int(max_iter * 1.5))

        best_result = None
        n_restarts = self.n_restarts

        for i in range(n_restarts):
            restart_seed = seed + i * 1000

            # Alternate between DE strategies across restarts
            # to diversify exploration of the search space
            strategies = ['best1bin', 'rand1bin', 'currenttobest1bin',
                          'best2bin', 'rand2bin']
            strategy = strategies[i % len(strategies)]

            result = differential_evolution(
                self.evaluate,
                bounds=bounds,
                maxiter=effective_iter,
                popsize=effective_pop,
                tol=tol,
                seed=restart_seed,
                callback=callback,
                disp=False,
                polish=True,
                strategy=strategy,
                mutation=(0.5, 1.5),
                recombination=0.9,
                init='latinhypercube',
            )

            if best_result is None or result.fun < best_result.fun:
                best_result = result

        return self._build_solution(best_result)

    def _build_solution(self, opt_result: OptimizeResult) -> Dict:
        """Build a detailed solution dict from optimization result."""
        x = opt_result.x
        params = self.decode(x)

        # Re-evaluate with detailed breakdown
        legs = []
        t0 = params['t0']
        tofs = params['tofs']

        current_time = t0
        v_inf_dir = params['v_inf_dir']
        v_inf_mag = params['v_inf_mag']

        dep_state = get_body_state(self.sequence[0], t0)
        current_v = dep_state[3:] + v_inf_mag * v_inf_dir

        total_dv = v_inf_mag  # departure

        for leg in range(self.n_legs):
            tof = tofs[leg]
            arrival_time = current_time + tof

            r1 = get_body_state(self.sequence[leg], current_time)[:3]
            r2_state = get_body_state(self.sequence[leg + 1], arrival_time)
            r2 = r2_state[:3]
            v2_body = r2_state[3:]

            try:
                v1_lambert, v2_lambert = solve_lambert(r1, r2, tof, MU_SUN)
            except (ValueError, RuntimeError):
                legs.append({'error': 'Lambert failed'})
                current_time = arrival_time
                continue

            if leg == 0:
                dsm_dv = np.linalg.norm(v1_lambert - current_v)
            else:
                flyby_state = get_body_state(self.sequence[leg], current_time)
                v_inf_in = current_v - flyby_state[3:]
                v_inf_out = v1_lambert - flyby_state[3:]

                mu_flyby = self.body_props[leg]['mu']
                rp_min = self.body_props[leg].get('rp_min',
                         self.body_props[leg]['radius'] * 1.05)
                dsm_dv = self._compute_flyby_dv(v_inf_in, v_inf_out,
                                                 mu_flyby, rp_min)

            total_dv += dsm_dv

            leg_info = {
                'from': self.sequence[leg],
                'to': self.sequence[leg + 1],
                'departure_et': current_time,
                'arrival_et': arrival_time,
                'tof_days': tof / 86400,
                'dsm_dv': dsm_dv,
                'r1': r1.tolist(),
                'r2': r2.tolist(),
                'v1_transfer': v1_lambert.tolist(),
                'v2_transfer': v2_lambert.tolist(),
            }
            legs.append(leg_info)

            current_time = arrival_time
            current_v = v2_lambert

        # Final arrival
        v_inf_arr = np.linalg.norm(current_v - v2_body)
        total_dv += v_inf_arr

        from .ephemeris import et_to_utc

        return {
            'sequence': self.sequence,
            'total_dv': opt_result.fun,
            'departure_v_inf': v_inf_mag,
            'arrival_v_inf': v_inf_arr,
            'c3_launch': v_inf_mag**2,
            'departure_utc': et_to_utc(t0),
            'arrival_utc': et_to_utc(current_time),
            'total_tof_days': sum(tof / 86400 for tof in tofs),
            'legs': legs,
            'optimizer': {
                'success': opt_result.success,
                'message': opt_result.message,
                'n_evaluations': opt_result.nfev,
                'best_dv': opt_result.fun,
            },
            'x': opt_result.x.tolist(),
        }


def optimize_earth_mars(dep_start: str = '2026-08-01',
                        dep_end: str = '2027-02-01',
                        tof_min: float = 150, tof_max: float = 400,
                        **kwargs) -> Dict:
    """Convenience: optimize a direct Earth-Mars transfer."""
    prob = MGATrajectory(
        sequence=['earth', 'mars'],
        dep_window=(dep_start, dep_end),
        tof_bounds=[(tof_min, tof_max)],
        v_inf_max=6.0,
    )
    return prob.optimize(**kwargs)


def optimize_earth_venus_mars(dep_start: str = '2026-01-01',
                              dep_end: str = '2028-01-01',
                              **kwargs) -> Dict:
    """Convenience: optimize Earth-Venus-Mars with Venus gravity assist."""
    prob = MGATrajectory(
        sequence=['earth', 'venus', 'mars'],
        dep_window=(dep_start, dep_end),
        tof_bounds=[(60, 300), (100, 500)],
        v_inf_max=8.0,
    )
    return prob.optimize(**kwargs)
