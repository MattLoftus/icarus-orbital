#!/usr/bin/env python3
"""Phase 1 validation: test Lambert solver, ephemeris, and porkchop generation
against known textbook and mission values."""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from src.core.ephemeris import (
    load_kernels, utc_to_et, et_to_utc,
    get_body_state, get_body_position
)
from src.core.lambert import solve_lambert
from src.core.flyby import compute_flyby, max_free_dv, max_deflection
from src.core.constants import MU_SUN, MU_EARTH, MU_JUPITER, R_JUPITER


def test_spice_kernels():
    """Test that SPICE kernels load and return sane values."""
    print("=" * 60)
    print("TEST 1: SPICE Kernel Loading + Ephemeris")
    print("=" * 60)

    load_kernels()
    print("  [OK] Kernels loaded successfully")

    # Earth position at J2000 epoch
    et_j2000 = utc_to_et('2000-01-01T12:00:00')
    earth_state = get_body_state('earth', et_j2000)
    earth_r = np.linalg.norm(earth_state[:3])
    earth_v = np.linalg.norm(earth_state[3:])

    print(f"  Earth at J2000:")
    print(f"    Position: [{earth_state[0]:.1f}, {earth_state[1]:.1f}, {earth_state[2]:.1f}] km")
    print(f"    Distance from Sun: {earth_r:.0f} km ({earth_r / 1.496e8:.4f} AU)")
    print(f"    Velocity: {earth_v:.2f} km/s")

    # Earth should be ~1 AU from Sun, moving at ~30 km/s
    assert 0.98 < earth_r / 1.496e8 < 1.02, f"Earth distance {earth_r/1.496e8:.4f} AU not ~1 AU"
    assert 28 < earth_v < 32, f"Earth velocity {earth_v:.2f} km/s not ~30 km/s"
    print("  [OK] Earth position/velocity within expected bounds")

    # Mars position
    mars_state = get_body_state('mars', et_j2000)
    mars_r = np.linalg.norm(mars_state[:3]) / 1.496e8  # AU
    print(f"  Mars at J2000: {mars_r:.4f} AU from Sun")
    assert 1.38 < mars_r < 1.67, f"Mars distance {mars_r:.4f} AU outside expected range"
    print("  [OK] Mars position within expected bounds")
    print()


def test_lambert_hohmann():
    """Test Lambert solver against Hohmann transfer Earth->Mars."""
    print("=" * 60)
    print("TEST 2: Lambert Solver — Earth-Mars Hohmann Transfer")
    print("=" * 60)

    # Use a known Earth-Mars opportunity
    # 2026-11-26 is near a Mars opposition window
    dep_date = '2026-11-15T00:00:00'
    arr_date = '2027-08-01T00:00:00'  # ~260 days, roughly Hohmann-like

    et_dep = utc_to_et(dep_date)
    et_arr = utc_to_et(arr_date)
    tof = et_arr - et_dep

    earth_state = get_body_state('earth', et_dep)
    mars_state = get_body_state('mars', et_arr)

    r1 = earth_state[:3]
    v1_earth = earth_state[3:]
    r2 = mars_state[:3]
    v2_mars = mars_state[3:]

    print(f"  Departure: {dep_date}")
    print(f"  Arrival:   {arr_date}")
    print(f"  TOF:       {tof/86400:.1f} days")

    v1_transfer, v2_transfer = solve_lambert(r1, r2, tof, MU_SUN)

    # Compute delta-v
    dv_dep = np.linalg.norm(v1_transfer - v1_earth)
    dv_arr = np.linalg.norm(v2_transfer - v2_mars)
    dv_total = dv_dep + dv_arr

    print(f"  Departure delta-v: {dv_dep:.3f} km/s")
    print(f"  Arrival delta-v:   {dv_arr:.3f} km/s")
    print(f"  Total delta-v:     {dv_total:.3f} km/s")
    print(f"  C3 launch:         {dv_dep**2:.2f} km^2/s^2")

    # Typical Earth-Mars transfers: 3.5-7.5 km/s total
    # Hohmann minimum is ~5.6 km/s but real windows vary
    assert 3.0 < dv_total < 15.0, f"Total delta-v {dv_total:.3f} km/s outside expected 3-15 km/s range"
    print(f"  [OK] Total delta-v {dv_total:.3f} km/s is within plausible range")

    # Verify Lambert solution consistency: propagating from r1 with v1 should reach r2
    # Check that the transfer orbit passes through both endpoints
    # (Kepler's equation check — simplified: just verify the f, g coefficients)
    r1_check = r1  # by construction
    r2_from_fg = r1 * (1 - np.linalg.norm(r2) / np.linalg.norm(r1)) + \
                 v1_transfer * tof  # rough check
    # More rigorous: verify angular momentum conservation
    h1 = np.cross(r1, v1_transfer)
    h2 = np.cross(r2, v2_transfer)
    h_diff = np.linalg.norm(h1 - h2) / np.linalg.norm(h1)
    print(f"  Angular momentum consistency: {h_diff:.2e} (should be ~0)")
    assert h_diff < 0.01, f"Angular momentum mismatch: {h_diff:.2e}"
    print("  [OK] Angular momentum conserved in transfer orbit")
    print()


def test_lambert_earth_venus():
    """Test Lambert solver for an Earth-Venus transfer."""
    print("=" * 60)
    print("TEST 3: Lambert Solver — Earth-Venus Transfer")
    print("=" * 60)

    dep_date = '2026-06-01T00:00:00'
    arr_date = '2026-10-15T00:00:00'  # ~136 days

    et_dep = utc_to_et(dep_date)
    et_arr = utc_to_et(arr_date)
    tof = et_arr - et_dep

    earth_state = get_body_state('earth', et_dep)
    venus_state = get_body_state('venus', et_arr)

    v1, v2 = solve_lambert(earth_state[:3], venus_state[:3], tof, MU_SUN)

    dv_dep = np.linalg.norm(v1 - earth_state[3:])
    dv_arr = np.linalg.norm(v2 - venus_state[3:])
    dv_total = dv_dep + dv_arr

    print(f"  TOF: {tof/86400:.1f} days")
    print(f"  Total delta-v: {dv_total:.3f} km/s")

    # Earth-Venus transfers typically 3-8 km/s
    assert 2.0 < dv_total < 20.0, f"Venus transfer dv {dv_total:.3f} outside range"
    print(f"  [OK] Earth-Venus delta-v plausible")
    print()


def test_flyby_jupiter():
    """Test gravity assist computation for a Jupiter flyby."""
    print("=" * 60)
    print("TEST 4: Gravity Assist — Jupiter Flyby")
    print("=" * 60)

    # Voyager-like scenario: spacecraft approaching Jupiter
    # Jupiter orbital velocity ~13.1 km/s
    v_jupiter = np.array([0.0, 13.1, 0.0])  # simplified, along +y

    # Spacecraft incoming at ~10 km/s relative to Jupiter
    v_inf_mag = 10.0  # km/s
    v_spacecraft = v_jupiter + np.array([v_inf_mag, 0.0, 0.0])

    # Periapsis at 2 Jupiter radii
    rp = 2.0 * R_JUPITER

    v_out, delta, dv_free = compute_flyby(
        v_spacecraft, v_jupiter, MU_JUPITER, rp, theta=0.0
    )

    delta_deg = np.degrees(delta)
    v_in_mag = np.linalg.norm(v_spacecraft)
    v_out_mag = np.linalg.norm(v_out)

    print(f"  V-infinity: {v_inf_mag:.1f} km/s")
    print(f"  Periapsis:  {rp:.0f} km ({rp/R_JUPITER:.1f} Rj)")
    print(f"  Deflection: {delta_deg:.1f} degrees")
    print(f"  Free dv:    {dv_free:.2f} km/s")
    print(f"  Speed in:   {v_in_mag:.2f} km/s -> Speed out: {v_out_mag:.2f} km/s")

    # Jupiter can provide large deflections. At 10 km/s v_inf and 2Rj:
    # e = 1 + rp * vinf^2 / mu = 1 + 139822 * 100 / 1.267e8 ~ 1.11
    # delta = 2 * arcsin(1/1.11) ~ 2 * 64.2 ~ 128 degrees
    assert 20 < delta_deg < 180, f"Deflection {delta_deg:.1f} deg outside range"
    assert dv_free > 1.0, f"Free dv {dv_free:.2f} km/s too low for Jupiter"

    # Max possible free dv from Jupiter at this v-infinity
    max_dv = max_free_dv(v_inf_mag, MU_JUPITER, R_JUPITER * 1.1)
    print(f"  Max possible free dv (1.1 Rj periapsis): {max_dv:.2f} km/s")

    print(f"  [OK] Jupiter flyby mechanics working correctly")
    print()


def test_porkchop_small():
    """Test porkchop generation with a small grid."""
    print("=" * 60)
    print("TEST 5: Porkchop Plot — Earth-Mars (small grid)")
    print("=" * 60)

    from src.core.porkchop import generate_porkchop, find_optimal_transfer

    t0 = time.time()
    data = generate_porkchop(
        'earth', 'mars',
        '2026-08-01', '2027-02-01',
        '2027-04-01', '2027-12-01',
        dep_steps=30, arr_steps=30,
    )
    elapsed = time.time() - t0

    valid_count = np.sum(np.isfinite(data['dv_total']))
    total_count = data['dv_total'].size
    valid_pct = 100 * valid_count / total_count

    print(f"  Grid: 30x30 = {total_count} points")
    print(f"  Valid solutions: {valid_count} ({valid_pct:.0f}%)")
    print(f"  Computation time: {elapsed:.1f}s")
    print(f"  Rate: {total_count/elapsed:.0f} Lambert solves/sec")

    # Find optimal
    optimal = find_optimal_transfer(data)
    if optimal:
        print(f"  Optimal transfer:")
        print(f"    Departure: {optimal['dep_utc']}")
        print(f"    Arrival:   {optimal['arr_utc']}")
        print(f"    Total dv:  {optimal['dv_total']:.3f} km/s")
        print(f"    C3:        {optimal['c3_launch']:.2f} km^2/s^2")
        print(f"    TOF:       {optimal['tof_days']:.0f} days")
        assert 3.0 < optimal['dv_total'] < 15.0, "Optimal dv outside range"
        print(f"  [OK] Optimal transfer found with plausible delta-v")
    else:
        print("  [WARN] No valid transfers found")

    # Delta-v range
    valid_dv = data['dv_total'][np.isfinite(data['dv_total'])]
    if len(valid_dv) > 0:
        print(f"  Delta-v range: {np.min(valid_dv):.2f} — {np.max(valid_dv):.2f} km/s")

    print()


def main():
    print()
    print("Orbital Mechanics — Phase 1 Validation")
    print("=" * 60)
    print()

    tests = [
        ("SPICE Kernels", test_spice_kernels),
        ("Lambert (Earth-Mars)", test_lambert_hohmann),
        ("Lambert (Earth-Venus)", test_lambert_earth_venus),
        ("Jupiter Flyby", test_flyby_jupiter),
        ("Porkchop Plot", test_porkchop_small),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
