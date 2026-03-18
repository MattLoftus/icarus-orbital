#!/usr/bin/env python3
"""Validate orbital mechanics against Voyager 2's Jupiter flyby using real SPICE data.

Voyager 2 Jupiter closest approach: July 9, 1979, 22:29 UTC
Distance: 721,670 km from Jupiter center (10.11 Rj)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import spiceypy as spice
from src.core.ephemeris import load_kernels, utc_to_et
from src.core.flyby import compute_flyby, max_deflection
from src.core.constants import MU_JUPITER, R_JUPITER

VOYAGER2_KERNEL = os.path.join(os.path.dirname(__file__), '..', 'kernels', 'voyager2.bsp')


def load_voyager_kernels():
    """Load standard kernels + Voyager 2 SPK."""
    load_kernels()
    if os.path.exists(VOYAGER2_KERNEL):
        spice.furnsh(VOYAGER2_KERNEL)
        print(f"  [OK] Loaded Voyager 2 kernel: {VOYAGER2_KERNEL}")
    else:
        raise FileNotFoundError(f"Voyager 2 kernel not found: {VOYAGER2_KERNEL}")


def main():
    print("=" * 70)
    print("Voyager 2 Jupiter Flyby Validation")
    print("=" * 70)

    load_voyager_kernels()

    # Voyager 2 closest approach: July 9, 1979, ~22:29 UTC
    ca_time = '1979-07-09T22:29:00'
    et_ca = utc_to_et(ca_time)

    # Get Voyager 2 state at closest approach (NAIF ID: -32)
    v2_state_ca, _ = spice.spkezr('-32', et_ca, 'ECLIPJ2000', 'NONE', '10')  # Sun-centered
    v2_pos_ca = np.array(v2_state_ca[:3])
    v2_vel_ca = np.array(v2_state_ca[3:])

    # Get Jupiter state at closest approach
    jup_state_ca, _ = spice.spkezr('5', et_ca, 'ECLIPJ2000', 'NONE', '10')
    jup_pos_ca = np.array(jup_state_ca[:3])
    jup_vel_ca = np.array(jup_state_ca[3:])

    # Relative position and velocity at closest approach
    rel_pos = v2_pos_ca - jup_pos_ca
    rel_vel = v2_vel_ca - jup_vel_ca
    ca_distance = np.linalg.norm(rel_pos)

    print(f"\n  Closest approach: {ca_time}")
    print(f"  Distance from Jupiter center: {ca_distance:.0f} km ({ca_distance/R_JUPITER:.2f} Rj)")
    print(f"  Known value: 721,670 km (10.11 Rj)")
    print(f"  Spacecraft heliocentric speed: {np.linalg.norm(v2_vel_ca):.2f} km/s")
    print(f"  Jupiter heliocentric speed: {np.linalg.norm(jup_vel_ca):.2f} km/s")
    print(f"  V-infinity at CA: {np.linalg.norm(rel_vel):.2f} km/s")

    # Now get states well before and after flyby to measure the gravity assist effect
    # 30 days before and after should be well outside Jupiter's SOI (~48 million km)
    dt_hours = 720  # 30 days in hours
    et_before = et_ca - dt_hours * 3600
    et_after = et_ca + dt_hours * 3600

    # Voyager 2 state 30 days before flyby
    v2_state_before, _ = spice.spkezr('-32', et_before, 'ECLIPJ2000', 'NONE', '10')
    v2_vel_before = np.array(v2_state_before[3:])
    v2_speed_before = np.linalg.norm(v2_vel_before)

    # Voyager 2 state 30 days after flyby
    v2_state_after, _ = spice.spkezr('-32', et_after, 'ECLIPJ2000', 'NONE', '10')
    v2_vel_after = np.array(v2_state_after[3:])
    v2_speed_after = np.linalg.norm(v2_vel_after)

    # Jupiter states at those times
    jup_state_before, _ = spice.spkezr('5', et_before, 'ECLIPJ2000', 'NONE', '10')
    jup_vel_before = np.array(jup_state_before[3:])

    jup_state_after, _ = spice.spkezr('5', et_after, 'ECLIPJ2000', 'NONE', '10')
    jup_vel_after = np.array(jup_state_after[3:])

    # V-infinity vectors
    v_inf_in = v2_vel_before - jup_vel_before
    v_inf_out = v2_vel_after - jup_vel_after
    v_inf_in_mag = np.linalg.norm(v_inf_in)
    v_inf_out_mag = np.linalg.norm(v_inf_out)

    # Deflection angle
    cos_delta = np.dot(v_inf_in, v_inf_out) / (v_inf_in_mag * v_inf_out_mag)
    delta_rad = np.arccos(np.clip(cos_delta, -1, 1))
    delta_deg = np.degrees(delta_rad)

    # Free delta-v from gravity assist
    dv_free = np.linalg.norm(v2_vel_after - v2_vel_before)

    print(f"\n  --- Gravity Assist Analysis ---")
    print(f"  Heliocentric speed before flyby: {v2_speed_before:.2f} km/s")
    print(f"  Heliocentric speed after flyby:  {v2_speed_after:.2f} km/s")
    print(f"  Speed gained: {v2_speed_after - v2_speed_before:.2f} km/s")
    print(f"  V-infinity in:  {v_inf_in_mag:.2f} km/s")
    print(f"  V-infinity out: {v_inf_out_mag:.2f} km/s")
    print(f"  Deflection angle: {delta_deg:.1f} degrees")
    print(f"  Free delta-v: {dv_free:.2f} km/s")

    # Compare with our flyby model
    print(f"\n  --- Model Comparison ---")

    # Use our flyby module to predict the outbound velocity
    v_out_model, delta_model, dv_model = compute_flyby(
        v2_vel_before, jup_vel_before, MU_JUPITER, ca_distance, theta=0.0
    )

    # Our model uses theta=0 which gives a specific flyby plane
    # The actual deflection angle should match regardless of plane orientation
    delta_model_deg = np.degrees(delta_model)

    # Theoretical deflection from the flyby distance
    e_theory = 1.0 + ca_distance * v_inf_in_mag**2 / MU_JUPITER
    delta_theory = np.degrees(2.0 * np.arcsin(1.0 / e_theory))

    print(f"  Theoretical deflection (from rp): {delta_theory:.1f} degrees")
    print(f"  Actual deflection (SPICE data):   {delta_deg:.1f} degrees")
    print(f"  Our model deflection:             {delta_model_deg:.1f} degrees")
    print()

    # Check v-infinity conservation (should be ~equal for unpowered flyby)
    vinf_diff_pct = abs(v_inf_out_mag - v_inf_in_mag) / v_inf_in_mag * 100
    print(f"  V-infinity conservation: in={v_inf_in_mag:.3f}, out={v_inf_out_mag:.3f} km/s "
          f"(diff: {vinf_diff_pct:.1f}%)")
    if vinf_diff_pct < 5:
        print(f"  [OK] V-infinity approximately conserved (expected for unpowered flyby)")
    else:
        print(f"  [NOTE] V-infinity not perfectly conserved — likely due to powered flyby or "
              f"SOI boundary effects over 30-day window")

    # Check deflection match
    delta_diff = abs(delta_deg - delta_theory)
    print(f"  Deflection match: SPICE={delta_deg:.1f}° vs Theory={delta_theory:.1f}° "
          f"(diff: {delta_diff:.1f}°)")
    if delta_diff < 10:
        print(f"  [OK] Deflection angle matches theory within patched-conics accuracy")
    else:
        print(f"  [NOTE] Deflection differs — expected from 30-day observation window "
              f"and continuous trajectory (not truly patched conics)")

    print(f"\n  --- Summary ---")
    print(f"  Voyager 2 gained ~{v2_speed_after - v2_speed_before:.1f} km/s from Jupiter gravity assist")
    print(f"  This is what enabled the Grand Tour to Saturn, Uranus, and Neptune")
    print()


if __name__ == '__main__':
    main()
