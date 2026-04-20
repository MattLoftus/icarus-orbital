"""Pre-computed reference mission data for Voyager 2 and Cassini.

Provides hardcoded trajectory data suitable for frontend visualization
without requiring SPICE kernels. Planet positions use circular orbit
approximations; trajectory arcs are interpolated in polar coordinates.
"""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AU_KM = 1.495978707e8  # 1 AU in km

# Circular orbit parameters: (semi-major axis in AU, period in days, J2000 longitude in deg)
# J2000 longitudes are approximate mean longitudes at J2000.0 (2000-01-01 12:00 TT)
PLANET_ORBITS = {
    "Earth":   {"a_au": 1.000, "period_days": 365.25,  "lon_j2000": 100.46},
    "Venus":   {"a_au": 0.723, "period_days": 224.7,   "lon_j2000": 181.98},
    "Mercury": {"a_au": 0.387, "period_days": 87.97,   "lon_j2000": 252.25},
    "Mars":    {"a_au": 1.524, "period_days": 686.97,  "lon_j2000": 355.45},
    "Jupiter": {"a_au": 5.203, "period_days": 4332.6,  "lon_j2000": 34.40},
    "Saturn":  {"a_au": 9.537, "period_days": 10759.2, "lon_j2000": 49.94},
    "Uranus":  {"a_au": 19.19, "period_days": 30687.0, "lon_j2000": 313.23},
    "Neptune": {"a_au": 30.07, "period_days": 60190.0, "lon_j2000": 304.88},
    "Pluto":   {"a_au": 39.48, "period_days": 90560.0, "lon_j2000": 238.92},
}

J2000_EPOCH = datetime(2000, 1, 1, 12, 0, 0)

POINTS_PER_LEG = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _planet_position_km(body: str, date: datetime) -> List[float]:
    """Return approximate heliocentric [x, y, z] in km for *body* at *date*.

    Uses a circular orbit in the ecliptic plane (z=0).
    """
    orb = PLANET_ORBITS[body]
    dt_days = (date - J2000_EPOCH).total_seconds() / 86400.0
    mean_lon_rad = math.radians(orb["lon_j2000"]) + 2.0 * math.pi * dt_days / orb["period_days"]
    r_km = orb["a_au"] * AU_KM
    x = r_km * math.cos(mean_lon_rad)
    y = r_km * math.sin(mean_lon_rad)
    return [x, y, 0.0]


def _interpolate_arc(
    body_a: str,
    date_a: datetime,
    body_b: str,
    date_b: datetime,
    n_points: int = POINTS_PER_LEG,
) -> List[List[float]]:
    """Generate an approximate trajectory arc between two planetary encounters.

    Interpolates in polar coordinates (r, theta) between the departure and
    arrival positions, producing a smooth curve in the ecliptic plane.
    """
    pos_a = _planet_position_km(body_a, date_a)
    pos_b = _planet_position_km(body_b, date_b)

    r_a = math.sqrt(pos_a[0] ** 2 + pos_a[1] ** 2)
    theta_a = math.atan2(pos_a[1], pos_a[0])

    r_b = math.sqrt(pos_b[0] ** 2 + pos_b[1] ** 2)
    theta_b = math.atan2(pos_b[1], pos_b[0])

    # Choose the shorter angular direction for inner-to-outer transfers,
    # but for gravity-assist missions the spacecraft often travels >180 deg.
    # Use a simple heuristic: if the radial distance increases significantly,
    # allow the full prograde sweep.
    dtheta = theta_b - theta_a
    # Normalize to (-2pi, 2pi) — prefer prograde (positive) sweep
    if dtheta < 0:
        dtheta += 2.0 * math.pi
    # For legs that clearly go more than halfway around, add a full revolution
    # (not needed for these reference missions, but keeps it general)

    fracs = np.linspace(0.0, 1.0, n_points)
    points: List[List[float]] = []
    for f in fracs:
        theta = theta_a + f * dtheta
        r = r_a + f * (r_b - r_a)
        points.append([float(r * math.cos(theta)), float(r * math.sin(theta)), 0.0])
    return points


def _build_trajectory(events: List[Dict[str, Any]]) -> List[List[float]]:
    """Build the full trajectory path from a sequence of encounter events."""
    trajectory: List[List[float]] = []
    for i in range(len(events) - 1):
        ev_a = events[i]
        ev_b = events[i + 1]
        arc = _interpolate_arc(
            ev_a["body"], ev_a["_date_obj"],
            ev_b["body"], ev_b["_date_obj"],
        )
        # Avoid duplicating the junction point between legs
        if i > 0:
            arc = arc[1:]
        trajectory.extend(arc)
    return trajectory


# ---------------------------------------------------------------------------
# Mission definitions
# ---------------------------------------------------------------------------

def _voyager2() -> Dict[str, Any]:
    """Voyager 2 Grand Tour mission data."""
    events = [
        {
            "body": "Earth",
            "date": "1977-08-20",
            "type": "launch",
            "distance_km": None,
            "dv_gained_km_s": None,
            "_date_obj": datetime(1977, 8, 20),
        },
        {
            "body": "Jupiter",
            "date": "1979-07-09",
            "type": "flyby",
            "distance_km": 721670,
            "dv_gained_km_s": 10.0,
            "_date_obj": datetime(1979, 7, 9),
        },
        {
            "body": "Saturn",
            "date": "1981-08-26",
            "type": "flyby",
            "distance_km": 161000,
            "dv_gained_km_s": 5.5,
            "_date_obj": datetime(1981, 8, 26),
        },
        {
            "body": "Uranus",
            "date": "1986-01-24",
            "type": "flyby",
            "distance_km": 81500,
            "dv_gained_km_s": 2.2,
            "_date_obj": datetime(1986, 1, 24),
        },
        {
            "body": "Neptune",
            "date": "1989-08-25",
            "type": "flyby",
            "distance_km": 29240,
            "dv_gained_km_s": 1.5,
            "_date_obj": datetime(1989, 8, 25),
        },
    ]

    trajectory = _build_trajectory(events)

    public_events = _make_public_events(events)

    return {
        "name": "Voyager 2 Grand Tour",
        "description": (
            "Voyager 2 launched in 1977 and performed gravity assists at Jupiter, "
            "Saturn, Uranus, and Neptune — the only spacecraft to visit all four "
            "outer planets. A rare planetary alignment that occurs once every ~175 "
            "years made this grand tour possible."
        ),
        "sequence": ["Earth", "Jupiter", "Saturn", "Uranus", "Neptune"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _cassini() -> Dict[str, Any]:
    """Cassini-Huygens VVEJGA mission data."""
    events = [
        {
            "body": "Earth",
            "date": "1997-10-15",
            "type": "launch",
            "distance_km": None,
            "dv_gained_km_s": None,
            "_date_obj": datetime(1997, 10, 15),
        },
        {
            "body": "Venus",
            "date": "1998-04-26",
            "type": "flyby",
            "distance_km": 284,
            "dv_gained_km_s": 7.0,
            "_date_obj": datetime(1998, 4, 26),
        },
        {
            "body": "Venus",
            "date": "1999-06-24",
            "type": "flyby",
            "distance_km": 600,
            "dv_gained_km_s": 6.7,
            "_date_obj": datetime(1999, 6, 24),
        },
        {
            "body": "Earth",
            "date": "1999-08-18",
            "type": "flyby",
            "distance_km": 1171,
            "dv_gained_km_s": 5.5,
            "_date_obj": datetime(1999, 8, 18),
        },
        {
            "body": "Jupiter",
            "date": "2000-12-30",
            "type": "flyby",
            "distance_km": 9722890,
            "dv_gained_km_s": 2.0,
            "_date_obj": datetime(2000, 12, 30),
        },
        {
            "body": "Saturn",
            "date": "2004-07-01",
            "type": "arrival",
            "distance_km": None,
            "dv_gained_km_s": None,
            "_date_obj": datetime(2004, 7, 1),
        },
    ]

    trajectory = _build_trajectory(events)

    public_events = _make_public_events(events)

    return {
        "name": "Cassini VVEJGA",
        "description": (
            "The Cassini-Huygens spacecraft used a Venus-Venus-Earth-Jupiter "
            "gravity assist (VVEJGA) trajectory to reach Saturn in 2004. The "
            "complex series of inner-planet flybys built up enough energy to "
            "reach the outer solar system without an impossibly large launcher."
        ),
        "sequence": ["Earth", "Venus", "Venus", "Earth", "Jupiter", "Saturn"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _new_horizons() -> Dict[str, Any]:
    """New Horizons mission to Pluto via Jupiter gravity assist."""
    events = [
        {"body": "Earth", "date": "2006-01-19", "type": "launch",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(2006, 1, 19)},
        {"body": "Jupiter", "date": "2007-02-28", "type": "flyby",
         "distance_km": 2304535, "dv_gained_km_s": 4.0,
         "_date_obj": datetime(2007, 2, 28)},
        {"body": "Pluto", "date": "2015-07-14", "type": "flyby",
         "distance_km": 12500, "dv_gained_km_s": 0.0,
         "_date_obj": datetime(2015, 7, 14)},
    ]
    trajectory = _build_trajectory(events)
    public_events = _make_public_events(events)
    return {
        "name": "New Horizons",
        "description": (
            "New Horizons launched in 2006 as the fastest spacecraft ever at the time, "
            "reaching Jupiter in just 13 months for a gravity assist. It flew past Pluto "
            "in July 2015, returning the first close-up images of the dwarf planet and "
            "its moons after a 9.5-year journey."
        ),
        "sequence": ["Earth", "Jupiter", "Pluto"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _galileo() -> Dict[str, Any]:
    """Galileo VEEGA mission to Jupiter."""
    events = [
        {"body": "Earth", "date": "1989-10-18", "type": "launch",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(1989, 10, 18)},
        {"body": "Venus", "date": "1990-02-10", "type": "flyby",
         "distance_km": 16106, "dv_gained_km_s": 2.3,
         "_date_obj": datetime(1990, 2, 10)},
        {"body": "Earth", "date": "1990-12-08", "type": "flyby",
         "distance_km": 960, "dv_gained_km_s": 5.2,
         "_date_obj": datetime(1990, 12, 8)},
        {"body": "Earth", "date": "1992-12-08", "type": "flyby",
         "distance_km": 303, "dv_gained_km_s": 3.7,
         "_date_obj": datetime(1992, 12, 8)},
        {"body": "Jupiter", "date": "1995-12-07", "type": "arrival",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(1995, 12, 7)},
    ]
    trajectory = _build_trajectory(events)
    public_events = _make_public_events(events)
    return {
        "name": "Galileo VEEGA",
        "description": (
            "Galileo used a Venus-Earth-Earth gravity assist (VEEGA) trajectory to "
            "reach Jupiter in 1995. After the Challenger disaster grounded its original "
            "Centaur upper stage, the mission was redesigned to use a weaker IUS booster "
            "plus three gravity assists over six years to build enough energy for Jupiter."
        ),
        "sequence": ["Earth", "Venus", "Earth", "Earth", "Jupiter"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _mariner10() -> Dict[str, Any]:
    """Mariner 10 — first gravity assist mission."""
    events = [
        {"body": "Earth", "date": "1973-11-03", "type": "launch",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(1973, 11, 3)},
        {"body": "Venus", "date": "1974-02-05", "type": "flyby",
         "distance_km": 5768, "dv_gained_km_s": 2.6,
         "_date_obj": datetime(1974, 2, 5)},
        {"body": "Mercury", "date": "1974-03-29", "type": "flyby",
         "distance_km": 703, "dv_gained_km_s": 0.0,
         "_date_obj": datetime(1974, 3, 29)},
    ]
    trajectory = _build_trajectory(events)
    public_events = _make_public_events(events)
    return {
        "name": "Mariner 10",
        "description": (
            "Mariner 10 was the first spacecraft to use a gravity assist maneuver, "
            "flying past Venus in February 1974 to redirect toward Mercury. It was "
            "also the first mission to visit Mercury, returning images of the planet's "
            "heavily cratered surface. The concept was proposed by Giuseppe Colombo."
        ),
        "sequence": ["Earth", "Venus", "Mercury"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _juno() -> Dict[str, Any]:
    """Juno mission to Jupiter with Earth flyby."""
    events = [
        {"body": "Earth", "date": "2011-08-05", "type": "launch",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(2011, 8, 5)},
        {"body": "Earth", "date": "2013-10-09", "type": "flyby",
         "distance_km": 559, "dv_gained_km_s": 7.3,
         "_date_obj": datetime(2013, 10, 9)},
        {"body": "Jupiter", "date": "2016-07-05", "type": "arrival",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(2016, 7, 5)},
    ]
    trajectory = _build_trajectory(events)
    public_events = _make_public_events(events)
    return {
        "name": "Juno",
        "description": (
            "Juno launched in 2011 toward Mars orbit, then performed a deep space "
            "maneuver to swing back for an Earth gravity assist in 2013, gaining 7.3 km/s "
            "to reach Jupiter in 2016. It entered a polar orbit to study Jupiter's "
            "atmosphere, magnetic field, and interior structure."
        ),
        "sequence": ["Earth", "Earth", "Jupiter"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _pioneer10() -> Dict[str, Any]:
    """Pioneer 10 — first spacecraft to Jupiter."""
    events = [
        {"body": "Earth", "date": "1972-03-03", "type": "launch",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(1972, 3, 3)},
        {"body": "Jupiter", "date": "1973-12-03", "type": "flyby",
         "distance_km": 132252, "dv_gained_km_s": 11.0,
         "_date_obj": datetime(1973, 12, 3)},
    ]
    trajectory = _build_trajectory(events)
    public_events = _make_public_events(events)
    return {
        "name": "Pioneer 10",
        "description": (
            "Pioneer 10 was the first spacecraft to traverse the asteroid belt and "
            "fly past Jupiter, arriving in December 1973 after a 21-month direct "
            "transfer — no gravity assists needed. Its close flyby at 132,252 km "
            "provided the first close-up images of Jupiter and confirmed the planet's "
            "intense radiation belts."
        ),
        "sequence": ["Earth", "Jupiter"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _messenger() -> Dict[str, Any]:
    """MESSENGER mission to Mercury orbit."""
    events = [
        {"body": "Earth", "date": "2004-08-03", "type": "launch",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(2004, 8, 3)},
        {"body": "Earth", "date": "2005-08-02", "type": "flyby",
         "distance_km": 2347, "dv_gained_km_s": 0.0,
         "_date_obj": datetime(2005, 8, 2)},
        {"body": "Venus", "date": "2006-10-24", "type": "flyby",
         "distance_km": 2992, "dv_gained_km_s": 5.5,
         "_date_obj": datetime(2006, 10, 24)},
        {"body": "Venus", "date": "2007-06-05", "type": "flyby",
         "distance_km": 338, "dv_gained_km_s": 4.9,
         "_date_obj": datetime(2007, 6, 5)},
        {"body": "Mercury", "date": "2008-01-14", "type": "flyby",
         "distance_km": 200, "dv_gained_km_s": 2.3,
         "_date_obj": datetime(2008, 1, 14)},
        {"body": "Mercury", "date": "2008-10-06", "type": "flyby",
         "distance_km": 200, "dv_gained_km_s": 2.0,
         "_date_obj": datetime(2008, 10, 6)},
        {"body": "Mercury", "date": "2009-09-29", "type": "flyby",
         "distance_km": 228, "dv_gained_km_s": 1.8,
         "_date_obj": datetime(2009, 9, 29)},
        {"body": "Mercury", "date": "2011-03-18", "type": "arrival",
         "distance_km": None, "dv_gained_km_s": None,
         "_date_obj": datetime(2011, 3, 18)},
    ]
    trajectory = _build_trajectory(events)
    public_events = _make_public_events(events)
    return {
        "name": "MESSENGER",
        "description": (
            "MESSENGER used an extraordinarily complex series of six gravity assists — "
            "one Earth, two Venus, and three Mercury flybys — over nearly seven years to "
            "slow down enough to enter Mercury orbit. Reaching Mercury requires more Δv "
            "than leaving the solar system because the spacecraft must shed Earth's "
            "30 km/s orbital velocity to fall inward toward the Sun."
        ),
        "sequence": ["Earth", "Earth", "Venus", "Venus", "Mercury", "Mercury", "Mercury", "Mercury"],
        "events": public_events,
        "trajectory_positions": trajectory,
    }


def _make_public_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Strip internal _date_obj and add heliocentric positions."""
    public = []
    for ev in events:
        pub = {k: v for k, v in ev.items() if k != "_date_obj"}
        pub["heliocentric_position_km"] = _planet_position_km(ev["body"], ev["_date_obj"])
        public.append(pub)
    return public


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_MISSIONS: Optional[List[Dict[str, Any]]] = None


def _load_missions() -> List[Dict[str, Any]]:
    global _MISSIONS
    if _MISSIONS is None:
        _MISSIONS = [
            _voyager2(), _cassini(), _new_horizons(), _galileo(),
            _mariner10(), _juno(), _pioneer10(), _messenger(),
        ]
    return _MISSIONS


def get_reference_missions() -> List[Dict[str, Any]]:
    """Return a list of all pre-computed reference mission dicts."""
    return _load_missions()


def get_reference_mission(name: str) -> Optional[Dict[str, Any]]:
    """Return a single mission dict by name, or None if not found.

    Name matching is case-insensitive and supports partial matches.
    Tries classic reference missions first, then historical EP missions.
    """
    missions = _load_missions()
    name_lower = name.lower()
    for m in missions:
        if name_lower in m["name"].lower():
            return m

    # Fall back to historical electric propulsion / hybrid / sail missions
    return _get_historical_ep_mission(name)


# --- Historical electric propulsion / hybrid / solar sail missions ---
# Lazy-computed and cached because building trajectories is slow (30-60s each).

_HISTORICAL_EP_REGISTRY = {
    'dawn': ('Dawn (NASA, 2007-2018)', 'src.data.historical_ep_missions:build_dawn_mission'),
    'hayabusa2': ('Hayabusa2 (JAXA, 2014-2020)', 'src.data.historical_ep_missions:build_hayabusa2_mission'),
    'hayabusa': ('Hayabusa (JAXA, 2003-2010)', 'src.data.historical_ep_missions:build_hayabusa_mission'),
    'bepicolombo': ('BepiColombo (ESA/JAXA, 2018-2025)', 'src.data.historical_ep_missions:build_bepi_colombo_mission'),
    'psyche': ('Psyche (NASA, 2023-2029)', 'src.data.historical_ep_missions:build_psyche_mission'),
    'ikaros': ('IKAROS (JAXA, 2010)', 'src.data.historical_ep_missions:build_ikaros_mission'),
}

_HISTORICAL_EP_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_historical_ep_mission(name: str) -> Optional[Dict[str, Any]]:
    """Look up a historical EP mission by short id or full name, with caching."""
    name_lower = name.lower()

    # Try to match short key first
    for key, (full_name, _) in _HISTORICAL_EP_REGISTRY.items():
        if key == name_lower or name_lower in full_name.lower():
            if key in _HISTORICAL_EP_CACHE:
                return _HISTORICAL_EP_CACHE[key]
            # Import and call the builder
            module_name, func_name = _HISTORICAL_EP_REGISTRY[key][1].split(':')
            import importlib
            mod = importlib.import_module(module_name)
            builder = getattr(mod, func_name)
            mission = builder()
            _HISTORICAL_EP_CACHE[key] = mission
            return mission
    return None


def list_historical_ep_missions() -> List[Dict[str, Any]]:
    """Return metadata for all historical EP missions (without computing trajectories)."""
    return [
        {'id': key, 'name': full_name}
        for key, (full_name, _) in _HISTORICAL_EP_REGISTRY.items()
    ]
