"""Designed missions — pre-computed novel trajectories for instant visualization.

Each mission stores the optimized x* and propagates the trajectory on demand
(fast — just Kepler propagation + Lambert, no optimization).
"""

import numpy as np
from typing import Dict, List
from src.data.gtop_missions import _propagate_mga_1dsm


# Pre-computed best x* for each designed mission
_DESIGNED_MISSIONS = {
    'grand-tour-eejs': {
        'name': 'Grand Tour: E→E→J→S',
        'description': 'Optimal Earth-Earth-Jupiter-Saturn tour departing 2033. '
                       'The Earth resonance flyby builds energy before Jupiter, achieving '
                       '8.80 km/s total Δv with a very low launch C3 of 2.6 km²/s².',
        'sequence': ['earth', 'earth', 'jupiter', 'saturn'],
        'x': [12248.203813, 1.616608, 0.070901, 0.50416,
              461.740891, 1941.578033, 2473.944856,
              0.418931, 0.445399, 0.069147,
              1.100007, 21.36764,
              1.487614, 1.339465],
        'n_legs': 3,
        'add_vinf_dep': True,
    },
    'grand-tour-vejs': {
        'name': 'Grand Tour: E→V→E→J→S',
        'description': 'Venus-Earth-Jupiter-Saturn tour departing 2034. '
                       'Venus flyby provides the energy boost, C3 of just 1.0 km²/s². '
                       'Only 0.24 km/s more than the EEJS variant.',
        'sequence': ['earth', 'venus', 'earth', 'jupiter', 'saturn'],
        'x': [12636.000487, 1.00034, 0.611353, 0.360078,
              240.073852, 541.51752, 1189.764888, 2490.381147,
              0.384361, 0.213895, 0.15786, 0.010149,
              1.1, 1.100023, 13.614101,
              1.29984, 1.550665, -1.436206],
        'n_legs': 4,
        'add_vinf_dep': True,
    },
    'fast-jupiter-vej': {
        'name': 'Fast Jupiter: E→V→E→J',
        'description': 'Venus-Earth-Jupiter transfer arriving in just 4.6 years. '
                       'Ideal for a Europa Clipper-class mission. C3=1.0 km²/s², '
                       '10.18 km/s total Δv.',
        'sequence': ['earth', 'venus', 'earth', 'jupiter'],
        'x': [10319.886282, 1.010979, 0.301292, 0.517366,
              177.882975, 521.49126, 992.331918,
              0.010746, 0.860175, 0.010204,
              1.107739, 1.100002,
              1.922876, 1.652932],
        'n_legs': 3,
        'add_vinf_dep': True,
    },
    'jupiter-emaj': {
        'name': 'Jupiter via E→Ma→J',
        'description': 'Earth-Mars-Jupiter transfer departing 2034. Mars gravity assist '
                       'redirects toward Jupiter at lower cost than Venus. '
                       'Best overall: 10.07 km/s, C3=1.1 km²/s².',
        'sequence': ['earth', 'earth', 'mars', 'jupiter'],
        'x': [12604.97302, 1.02589, 1.0, 0.501917,
              474.121853, 549.054782, 1176.807684,
              0.462113, 0.502443, 0.099878,
              1.100008, 1.100014,
              1.357558, 1.465798],
        'n_legs': 3,
        'add_vinf_dep': True,
    },
    'jupiter-maej': {
        'name': 'Jupiter via Ma→E→J',
        'description': 'Mars-Earth-Jupiter transfer departing 2033. Flies out to Mars first, '
                       'returns to Earth for a gravity assist, then proceeds to Jupiter. '
                       '10.66 km/s, C3=1.0 km²/s².',
        'sequence': ['earth', 'mars', 'earth', 'jupiter'],
        'x': [12228.614228, 1.000724, 0.999998, 0.732295,
              405.421633, 787.262203, 1187.102962,
              0.027862, 0.556247, 0.063739,
              1.958891, 1.1,
              -0.885768, 1.529267],
        'n_legs': 3,
        'add_vinf_dep': True,
    },
}


# Sample return missions — stored x* values for pre-computed round-trip trajectories
_SAMPLE_RETURN_MISSIONS: Dict[str, Dict] = {
    'sample-return-sg344': {
        'name': 'Sample Return: 2000 SG344',
        'description': 'Extraordinarily low-delta-v sample return to 2000 SG344, '
                       'one of the most accessible NEAs in the NHATS database. '
                       'Total 1.83 km/s over 2.1 years — dramatically cheaper than any '
                       'flown sample return mission.',
        'designation': '2000 SG344',
        'x': [10262.706, 150.6001, 335.8358, 285.5855],
    },
    'sample-return-hu4': {
        'name': 'Sample Return: 2008 HU4',
        'description': 'Low-inclination near-Earth asteroid, 3.92 km/s total Δv. '
                       'Second-most accessible target tested.',
        'designation': '2008 HU4',
        'x': [12921.5851, 318.11, 32.6289, 345.3932],
    },
    'sample-return-ao10': {
        'name': 'Sample Return: 1999 AO10',
        'description': 'Accessible NEA with slightly eccentric orbit, 5.91 km/s total Δv.',
        'designation': '1999 AO10',
        'x': [11766.6872, 276.9613, 30.0, 280.8532],
    },
}

# Interstellar precursor missions (escape trajectory, maximize v_inf)
_INTERSTELLAR_MISSIONS: Dict[str, Dict] = {
    'interstellar-vej': {
        'name': 'Interstellar Precursor: VEJ',
        'description': 'Venus-Earth-Jupiter gravity assist chain maximizing escape velocity. '
                       'Reaches 35 km/s asymptotic (7.4 AU/yr) — 200 AU in 27 years. '
                       'Launch C3=12.9, total impulsive Δv 15 km/s (hard budget).',
        'sequence': ['earth', 'venus', 'earth', 'jupiter'],
        'x': [10735.5604, 3.5867, 0.406, 0.74, 388.0118, 379.3022, 1997.9112,
              0.4132, 0.0336, 0.8648, 1.5795, 1.8371, 7.6486,
              1.6623, -1.1969, 2.9647],
    },
}


# Multi-NEA tour missions (2-asteroid rendezvous tours)
_MULTI_NEA_MISSIONS: Dict[str, Dict] = {
    'tour-sg344-rh120': {
        'name': 'Tour: SG344 → RH120',
        'description': 'Two-asteroid rendezvous tour visiting 2000 SG344 then 2006 RH120 '
                       '(a "mini-moon" — temporarily captured near-Earth object). '
                       'Incredibly low 3.71 km/s total Δv over 2.5 years, less than half '
                       'the cost of a single-target Bennu sample return.',
        'ast1_designation': '2000 SG344',
        'ast2_designation': '2006 RH120',
        'x': [10262.7072, 150.6002, 42.4993, 290.4796, 137.7934, 291.546],
    },
}


def get_designed_mission(mission_id: str) -> Dict:
    """Get a designed mission trajectory, propagated from stored x*."""
    # Interstellar precursor
    if mission_id in _INTERSTELLAR_MISSIONS:
        from src.core.interstellar import propagate_interstellar_mission
        spec = _INTERSTELLAR_MISSIONS[mission_id]
        result = propagate_interstellar_mission(np.array(spec['x']), spec['sequence'])
        result['name'] = spec['name']
        result['description'] = spec['description']
        return result

    # Multi-NEA tour
    if mission_id in _MULTI_NEA_MISSIONS:
        from src.core.multi_nea_tour import propagate_2nea_mission
        from src.data.sbdb import fetch_asteroid_elements
        spec = _MULTI_NEA_MISSIONS[mission_id]
        el1 = fetch_asteroid_elements(spec['ast1_designation'])
        el2 = fetch_asteroid_elements(spec['ast2_designation'])
        if not (el1 and el2):
            return None
        result = propagate_2nea_mission(np.array(spec['x']), el1, el2)
        result['name'] = spec['name']
        result['description'] = spec['description']
        return result

    # Sample return
    if mission_id in _SAMPLE_RETURN_MISSIONS:
        from src.core.sample_return import propagate_sample_return_mission
        from src.data.sbdb import fetch_asteroid_elements
        spec = _SAMPLE_RETURN_MISSIONS[mission_id]
        elements = fetch_asteroid_elements(spec['designation'])
        if not elements:
            return None
        result = propagate_sample_return_mission(np.array(spec['x']), elements)
        result['name'] = spec['name']
        result['description'] = spec['description']
        return result

    if mission_id not in _DESIGNED_MISSIONS:
        return None

    spec = _DESIGNED_MISSIONS[mission_id]
    x = np.array(spec['x'])

    result = _propagate_mga_1dsm(
        x, spec['sequence'], spec['n_legs'],
        add_vinf_dep=spec['add_vinf_dep'],
    )

    result['name'] = spec['name']
    result['description'] = spec['description']

    return result


def list_designed_missions() -> List[Dict]:
    """List available designed missions (without computing trajectories)."""
    result = []
    for mid, spec in _DESIGNED_MISSIONS.items():
        seq_str = '→'.join(s[0].upper() if s != 'jupiter' else 'J' for s in spec['sequence'])
        # Fix abbreviations
        seq_str = seq_str.replace('E', 'E').replace('V', 'V').replace('M', 'Ma').replace('J', 'J').replace('S', 'S')
        result.append({
            'id': mid,
            'name': spec['name'],
            'sequence': '→'.join(s.title() for s in spec['sequence']),
        })
    return result
