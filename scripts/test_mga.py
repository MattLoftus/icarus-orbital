#!/usr/bin/env python3
"""Test MGA trajectory optimizer — Earth-Mars direct transfer."""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.mga import MGATrajectory, optimize_earth_mars


def test_earth_mars_direct():
    """Optimize a direct Earth-Mars transfer for the 2026 window."""
    print("=" * 60)
    print("MGA Optimizer: Earth-Mars Direct (2026 window)")
    print("=" * 60)

    t0 = time.time()

    # Use smaller population for faster test
    result = optimize_earth_mars(
        dep_start='2026-08-01',
        dep_end='2027-02-01',
        tof_min=150,
        tof_max=400,
        max_iter=200,
        pop_size=20,
        seed=42,
    )

    elapsed = time.time() - t0

    print(f"\n  Optimization completed in {elapsed:.1f}s")
    print(f"  Function evaluations: {result['optimizer']['n_evaluations']}")
    print(f"  Success: {result['optimizer']['success']}")
    print(f"  Message: {result['optimizer']['message']}")
    print()
    print(f"  Sequence: {' → '.join(result['sequence'])}")
    print(f"  Departure: {result['departure_utc']}")
    print(f"  Arrival:   {result['arrival_utc']}")
    print(f"  Total TOF: {result['total_tof_days']:.1f} days")
    print()
    print(f"  Departure v-inf: {result['departure_v_inf']:.3f} km/s")
    print(f"  C3 launch:       {result['c3_launch']:.2f} km^2/s^2")
    print(f"  Arrival v-inf:   {result['arrival_v_inf']:.3f} km/s")
    print(f"  Total delta-v:   {result['total_dv']:.3f} km/s")
    print()

    for i, leg in enumerate(result['legs']):
        if 'error' in leg:
            print(f"  Leg {i+1}: ERROR - {leg['error']}")
        else:
            print(f"  Leg {i+1}: {leg['from']} → {leg['to']}")
            print(f"    TOF: {leg['tof_days']:.1f} days")
            print(f"    DSM: {leg['dsm_dv']:.3f} km/s")

    # Sanity check: should be in the 5-8 km/s range for Earth-Mars
    if result['total_dv'] < 15:
        print(f"\n  [OK] Total delta-v {result['total_dv']:.3f} km/s is plausible")
    else:
        print(f"\n  [WARN] Total delta-v {result['total_dv']:.3f} km/s seems high")

    return result


def test_earth_venus_mars():
    """Optimize Earth-Venus-Mars with Venus gravity assist."""
    print("\n" + "=" * 60)
    print("MGA Optimizer: Earth-Venus-Mars (Venus gravity assist)")
    print("=" * 60)

    prob = MGATrajectory(
        sequence=['earth', 'venus', 'mars'],
        dep_window=('2026-01-01', '2027-06-01'),
        tof_bounds=[(80, 250), (150, 400)],
        v_inf_max=5.0,
    )

    t0 = time.time()
    result = prob.optimize(max_iter=300, pop_size=30, seed=123)
    elapsed = time.time() - t0

    print(f"\n  Optimization completed in {elapsed:.1f}s")
    print(f"  Function evaluations: {result['optimizer']['n_evaluations']}")
    print(f"  Sequence: {' → '.join(result['sequence'])}")
    print(f"  Departure: {result['departure_utc']}")
    print(f"  Arrival:   {result['arrival_utc']}")
    print(f"  Total TOF: {result['total_tof_days']:.1f} days")
    print(f"  Total delta-v: {result['total_dv']:.3f} km/s")
    print()

    for i, leg in enumerate(result['legs']):
        if 'error' not in leg:
            print(f"  Leg {i+1}: {leg['from']} → {leg['to']} ({leg['tof_days']:.0f}d, DSM: {leg['dsm_dv']:.3f} km/s)")

    return result


if __name__ == '__main__':
    r1 = test_earth_mars_direct()
    r2 = test_earth_venus_mars()

    print("\n" + "=" * 60)
    print("Comparison:")
    print(f"  Direct Earth-Mars:       {r1['total_dv']:.3f} km/s ({r1['total_tof_days']:.0f} days)")
    print(f"  Earth-Venus-Mars (GA):   {r2['total_dv']:.3f} km/s ({r2['total_tof_days']:.0f} days)")
    if r2['total_dv'] < r1['total_dv']:
        savings = r1['total_dv'] - r2['total_dv']
        print(f"  Venus gravity assist saves {savings:.3f} km/s ({100*savings/r1['total_dv']:.1f}%)")
    print("=" * 60)
