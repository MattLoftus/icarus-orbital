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
}


def get_designed_mission(mission_id: str) -> Dict:
    """Get a designed mission trajectory, propagated from stored x*."""
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
