#!/usr/bin/env python3
"""Test NHATS API integration — fetch most accessible NEA targets."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.data.nhats import fetch_and_cache_targets, print_target_summary
from src.data.sbdb import fetch_asteroid_elements


def main():
    # Fetch targets with delta-v < 6 km/s (most accessible)
    print("Fetching NHATS targets (delta-v < 6 km/s)...")
    targets = fetch_and_cache_targets(max_dv=6)
    print(f"\nFound {len(targets)} accessible targets with delta-v < 6 km/s")

    print_target_summary(targets, n=20)

    # Fetch orbital elements for a well-known accessible target
    # Pick 2000 SG344 — a notable, well-characterized accessible NEA
    test_target = next((t for t in targets if 'SG344' in t['des']), targets[0])
    if targets:
        best = test_target
        print(f"\nFetching orbital elements for {best['des']}...")
        elements = fetch_asteroid_elements(best['des'])
        if elements:
            print(f"  Name: {elements.get('name')}")
            print(f"  Class: {elements.get('orbit_class')}")
            print(f"  a = {elements.get('a', 0):.4f} AU")
            print(f"  e = {elements.get('e', 0):.4f}")
            print(f"  i = {elements.get('i', 0):.2f} deg")
            print(f"  H = {elements.get('h_mag', 0):.1f}")
        else:
            print(f"  Could not fetch elements for {best['des']}")


if __name__ == '__main__':
    main()
