"""NASA NHATS (Near-Earth Object Human Space Flight Accessible Targets Study) API client.

Queries the NHATS REST API for accessible NEA targets with trajectory data.
API docs: https://ssd-api.jpl.nasa.gov/doc/nhats.html
"""

import requests
import json
import os
from typing import Dict, List, Optional

NHATS_API_URL = 'https://ssd-api.jpl.nasa.gov/nhats.api'
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data_cache')


def fetch_accessible_targets(max_dv: int = 12, max_dur: int = 450,
                             min_stay: int = 8,
                             launch_window: str = '2025-2040'
                             ) -> Dict:
    """Fetch all NHATS-accessible targets matching constraints.

    Args:
        max_dv: Maximum total delta-v in km/s (options: 4-12)
        max_dur: Maximum mission duration in days (options: 60-450)
        min_stay: Minimum stay at asteroid in days (options: 8, 16, 24, 32)
        launch_window: Launch window range (e.g., '2025-2040')

    Returns:
        Dict with 'count' and 'data' (list of target records)
    """
    params = {
        'dv': max_dv,
        'dur': max_dur,
        'stay': min_stay,
    }
    resp = requests.get(NHATS_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_target_details(designation: str) -> Dict:
    """Fetch detailed trajectory data for a single NHATS target.

    Args:
        designation: Asteroid designation (e.g., '2009 HC', '101955' for Bennu)

    Returns:
        Dict with trajectory windows, min delta-v, orbit data
    """
    params = {'des': designation}
    resp = requests.get(NHATS_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_and_cache_targets(max_dv: int = 12, force_refresh: bool = False) -> List[Dict]:
    """Fetch targets and cache locally to avoid repeated API calls.

    Returns:
        List of target dicts with keys: des, fullname, h (abs magnitude),
        min_dv, min_dur, n_via (number of viable trajectories), etc.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f'nhats_dv{max_dv}.json')

    if not force_refresh and os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)

    print(f"Fetching NHATS targets (max dv={max_dv} km/s)...")
    data = fetch_accessible_targets(max_dv=max_dv)

    targets = []
    if 'data' in data:
        for entry in data['data']:
            min_dv_data = entry.get('min_dv', {})
            min_dur_data = entry.get('min_dur', {})
            target = {
                'des': entry.get('des', ''),
                'fullname': entry.get('fullname', '').strip(),
                'h': float(entry.get('h', 99)),
                'min_dv': float(min_dv_data.get('dv', 999) if isinstance(min_dv_data, dict) else 999),
                'min_dv_dur': float(min_dv_data.get('dur', 9999) if isinstance(min_dv_data, dict) else 9999),
                'min_dur': float(min_dur_data.get('dur', 9999) if isinstance(min_dur_data, dict) else 9999),
                'min_dur_dv': float(min_dur_data.get('dv', 999) if isinstance(min_dur_data, dict) else 999),
                'n_via': int(entry.get('n_via_traj', 0)),
                'occ': int(entry.get('occ', 9)),
                'min_size_m': float(entry.get('min_size', 0) or 0),
                'max_size_m': float(entry.get('max_size', 0) or 0),
            }
            # Estimate size from absolute magnitude
            # D(km) = 1329 / sqrt(albedo) * 10^(-H/5)
            # Assume albedo = 0.14 (typical S-type)
            target['size_est_m'] = 1329e3 / (0.14**0.5) * 10**(-target['h'] / 5)
            targets.append(target)

    # Sort by minimum delta-v
    targets.sort(key=lambda t: t['min_dv'])

    with open(cache_file, 'w') as f:
        json.dump(targets, f)

    print(f"  Cached {len(targets)} targets to {cache_file}")
    return targets


def get_most_accessible(n: int = 20, max_dv: int = 6) -> List[Dict]:
    """Get the N most accessible NEA targets (lowest delta-v).

    Args:
        n: Number of targets to return
        max_dv: Maximum delta-v filter

    Returns:
        List of target dicts sorted by min_dv
    """
    targets = fetch_and_cache_targets(max_dv=max_dv)
    return targets[:n]


def print_target_summary(targets: List[Dict], n: int = 20):
    """Print a formatted summary of top targets."""
    print(f"\n{'Rank':<5} {'Designation':<15} {'Min Δv (km/s)':<15} {'Min Dur (d)':<13} "
          f"{'H mag':<8} {'Size (m)':<12} {'# Traj':<10}")
    print("-" * 78)
    for i, t in enumerate(targets[:n]):
        print(f"{i+1:<5} {t['des']:<15} {t['min_dv']:<15.3f} {t['min_dur']:<13.0f} "
              f"{t['h']:<8.1f} {t['size_est_m']:<12.0f} {t['n_via']:<10}")
