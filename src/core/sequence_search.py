"""Automated gravity assist sequence discovery.

Given a departure body and a destination, enumerate all physically viable
flyby sequences, pre-screen with quick Lambert evaluations, then run full
MGA optimization on the top candidates.

Three-tier pipeline:
  Tier 1: Combinatorial enumeration + physical pruning (~1ms)
  Tier 2: Lambert pre-screening at sampled epochs (~seconds)
  Tier 3: Full MGA-1DSM optimization on top candidates (~minutes)
"""

import itertools
import time
import numpy as np
from typing import List, Dict, Tuple, Optional
from .mga import MGATrajectory
from .lambert import solve_lambert
from .flyby import max_deflection
from .ephemeris import get_body_state, utc_to_et
from .constants import MU_SUN, BODIES

BODY_SMA = {
    'mercury': 0.387, 'venus': 0.723, 'earth': 1.000,
    'mars': 1.524, 'jupiter': 5.203, 'saturn': 9.537,
}

FLYBY_BODIES = ['venus', 'earth', 'mars', 'jupiter']


def estimate_leg_tof_bounds(from_body: str, to_body: str) -> Tuple[float, float]:
    """Estimate reasonable TOF bounds for a leg based on body pair."""
    sma_from = BODY_SMA.get(from_body, 1.0)
    sma_to = BODY_SMA.get(to_body, 1.0)
    sma_max = max(sma_from, sma_to)
    sma_min = min(sma_from, sma_to)

    if sma_max < 2.0:
        return (30, 400)
    elif sma_max < 6.0:
        return (200, 1500) if sma_min < 2.0 else (300, 2000)
    else:
        return (400, 2500) if sma_min < 2.0 else (600, 6000)


def estimate_leg_tof(from_body: str, to_body: str) -> float:
    """Estimate a typical TOF for a leg (days) — Hohmann-like."""
    a1 = BODY_SMA.get(from_body, 1.0)
    a2 = BODY_SMA.get(to_body, 1.0)
    a_t = (a1 + a2) / 2
    return np.sqrt(a_t**3) / 2 * 365.25  # Hohmann half-orbit in days


def generate_candidate_sequences(departure: str, destination: str,
                                 max_flybys: int = 3) -> List[List[str]]:
    """Generate all physically viable flyby sequences (Tier 1)."""
    departure = departure.lower()
    destination = destination.lower()
    sma_dep = BODY_SMA.get(departure, 1.0)
    sma_dest = BODY_SMA.get(destination, 1.0)
    outbound = sma_dest > sma_dep

    available = []
    for body in FLYBY_BODIES:
        if body == destination:
            continue
        if outbound:
            if BODY_SMA[body] < sma_dest * 0.8:
                available.append(body)
        else:
            if BODY_SMA[body] > sma_dest * 0.5:
                available.append(body)

    if departure not in available and departure in FLYBY_BODIES:
        available.append(departure)

    sequences = [[departure, destination]]

    for n_flybys in range(1, max_flybys + 1):
        for combo in itertools.product(available, repeat=n_flybys):
            seq = [departure] + list(combo) + [destination]
            if _is_valid_sequence(seq, outbound):
                sequences.append(seq)

    # Deduplicate
    seen = set()
    unique = []
    for seq in sequences:
        key = tuple(seq)
        if key not in seen:
            seen.add(key)
            unique.append(seq)

    return unique


def _is_valid_sequence(seq: List[str], outbound: bool) -> bool:
    """Physical pruning rules."""
    # No triple consecutive identical
    for i in range(len(seq) - 2):
        if seq[i] == seq[i + 1] == seq[i + 2]:
            return False
    # No immediate return to departure
    if len(seq) > 2 and seq[1] == seq[0]:
        return False
    # Outbound: last flyby shouldn't be too far inward
    if outbound and len(seq) > 3:
        last_flyby = seq[-2]
        if BODY_SMA.get(last_flyby, 1.0) < BODY_SMA.get(seq[0], 1.0) * 0.3:
            return False
    return True


def _lambert_prescreen(seq: List[str], dep_et: float, n_samples: int = 5) -> float:
    """Quick Lambert-based cost estimate for a sequence (Tier 2).

    Evaluates at a few departure epochs with Hohmann-like TOF estimates.
    Returns estimated total delta-v (km/s), or inf if infeasible.
    """
    n_legs = len(seq) - 1
    tofs = [estimate_leg_tof(seq[j], seq[j + 1]) * 86400 for j in range(n_legs)]

    best_cost = float('inf')

    for offset_days in np.linspace(0, 365, n_samples):
        t0 = dep_et + offset_days * 86400
        total_dv = 0.0
        feasible = True
        current_time = t0

        for leg in range(n_legs):
            tof = tofs[leg]
            try:
                r1 = get_body_state(seq[leg], current_time)[:3]
                arr_state = get_body_state(seq[leg + 1], current_time + tof)
                r2 = arr_state[:3]

                v1, v2 = solve_lambert(r1, r2, tof, MU_SUN)

                # Departure v-inf for first leg
                if leg == 0:
                    dep_state = get_body_state(seq[0], current_time)
                    total_dv += np.linalg.norm(v1 - dep_state[3:])

                # Arrival v-inf for last leg
                if leg == n_legs - 1:
                    total_dv += np.linalg.norm(v2 - arr_state[3:])

                # Check flyby feasibility at intermediate bodies
                if 0 < leg < n_legs:
                    flyby_body = seq[leg]
                    props = BODIES.get(flyby_body, {})
                    mu_fb = props.get('mu', 1e4)
                    rp_min = props.get('rp_min', props.get('radius', 6000) * 1.05)

                    flyby_state = get_body_state(flyby_body, current_time)
                    v_inf_in = v2 - flyby_state[3:]  # from previous leg
                    v_inf_mag = np.linalg.norm(v_inf_in)

                    # Check max deflection — if body can't deflect enough, penalize
                    delta_max = max_deflection(v_inf_mag, mu_fb, rp_min)
                    if delta_max < np.radians(5):
                        total_dv += 5.0  # heavy penalty for useless flyby

                current_time += tof
            except (ValueError, RuntimeError):
                feasible = False
                break

        if feasible and total_dv < best_cost:
            best_cost = total_dv

    return best_cost


def search_sequences(departure: str, destination: str,
                     dep_window: Tuple[str, str],
                     max_flybys: int = 3,
                     max_candidates: int = 50,
                     top_n_optimize: int = 10,
                     quick_iter: int = 150,
                     quick_pop: int = 20,
                     verbose: bool = True) -> Dict:
    """Search for the best gravity assist sequence to a destination.

    Three-tier pipeline:
      1. Enumerate + prune candidates
      2. Lambert pre-screen (cheap)
      3. Full MGA optimization on top candidates (expensive)
    """
    t_start = time.time()

    # Tier 1: Generate candidates
    candidates = generate_candidate_sequences(departure, destination, max_flybys)
    if verbose:
        print(f"Tier 1: {len(candidates)} candidate sequences")

    # Tier 2: Lambert pre-screening
    dep_et = utc_to_et(dep_window[0])
    prescreened = []
    for seq in candidates[:max_candidates]:
        cost = _lambert_prescreen(seq, dep_et, n_samples=5)
        prescreened.append((seq, cost))
        if verbose:
            seq_str = ' → '.join(seq)
            print(f"  Tier 2: {seq_str:40s} ~{cost:8.1f} km/s")

    # Sort by Lambert cost, take top N for full optimization
    prescreened.sort(key=lambda x: x[1])
    top_candidates = [s for s, _ in prescreened[:top_n_optimize]]

    if verbose:
        print(f"\nTier 3: Optimizing top {len(top_candidates)} candidates")

    # Tier 3: Full MGA optimization
    results = []
    for i, seq in enumerate(top_candidates):
        seq_str = ' → '.join(seq)
        n_legs = len(seq) - 1
        tof_bounds = [estimate_leg_tof_bounds(seq[j], seq[j + 1]) for j in range(n_legs)]

        try:
            prob = MGATrajectory(
                sequence=seq,
                dep_window=dep_window,
                tof_bounds=tof_bounds,
                v_inf_max=6.0,
                n_restarts=1,
            )
            result = prob.optimize(max_iter=quick_iter, pop_size=quick_pop, seed=42 + i)

            results.append({
                'sequence': seq,
                'sequence_str': seq_str,
                'n_flybys': n_legs - 1,
                'total_dv': result['total_dv'],
                'total_tof_days': result['total_tof_days'],
                'departure_utc': result['departure_utc'],
                'arrival_utc': result['arrival_utc'],
                'legs': result['legs'],
                'optimizer': result['optimizer'],
            })

            if verbose:
                status = '✓' if result['optimizer']['success'] else '✗'
                print(f"  [{i+1}/{len(top_candidates)}] {seq_str:40s} "
                      f"{result['total_dv']:8.3f} km/s  "
                      f"{result['total_tof_days']:6.0f}d {status}")

        except Exception as e:
            if verbose:
                print(f"  [{i+1}/{len(top_candidates)}] {seq_str:40s} FAILED: {e}")

    results.sort(key=lambda r: r['total_dv'])
    elapsed = time.time() - t_start

    return {
        'departure': departure,
        'destination': destination,
        'dep_window': dep_window,
        'n_candidates_generated': len(candidates),
        'n_prescreened': len(prescreened),
        'n_optimized': len(results),
        'elapsed_seconds': elapsed,
        'rankings': results,
        'best': results[0] if results else None,
    }
