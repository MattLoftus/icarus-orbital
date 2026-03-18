"""JPL Small-Body Database API client for asteroid orbital elements.

API docs: https://ssd-api.jpl.nasa.gov/doc/sbdb.html
"""

import requests
from typing import Dict, Optional


SBDB_API_URL = 'https://ssd-api.jpl.nasa.gov/sbdb.api'


def fetch_asteroid_elements(designation: str) -> Optional[Dict]:
    """Fetch orbital elements for a specific asteroid.

    Args:
        designation: Asteroid name or designation (e.g., 'Bennu', '2000 SG344')

    Returns:
        Dict with orbital elements, or None if not found.
    """
    params = {'sstr': designation}
    resp = requests.get(SBDB_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Check for "not found" response
    if 'message' in data and 'not found' in data.get('message', '').lower():
        return None

    if 'orbit' not in data or 'elements' not in data['orbit']:
        return None

    elements_list = data['orbit']['elements']
    elements = {}
    for el in elements_list:
        elements[el['name']] = el['value']

    obj = data.get('object', {})
    orbit = data.get('orbit', {})

    result = {
        'name': obj.get('fullname', designation),
        'des': obj.get('des', designation),
        'spkid': obj.get('spkid', ''),
        'neo': obj.get('neo', False),
        'pha': obj.get('pha', False),
        'orbit_id': orbit.get('orbit_id', ''),
        'condition_code': orbit.get('condition_code', ''),
        'moid_au': float(orbit.get('moid', 0) or 0),
    }

    # Parse orbital elements
    element_map = {
        'a': 'a', 'e': 'e', 'i': 'i', 'om': 'om', 'w': 'w',
        'ma': 'ma', 'tp': 'tp', 'per': 'per', 'n': 'n',
        'q': 'q', 'ad': 'ad',
    }
    for key, name in element_map.items():
        if name in elements:
            try:
                result[key] = float(elements[name])
            except (ValueError, TypeError):
                pass

    return result
