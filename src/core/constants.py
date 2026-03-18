"""Physical constants and body data for orbital mechanics."""

import os

# Gravitational parameters (km^3/s^2)
MU_SUN = 1.32712440018e11
MU_MERCURY = 2.2032e4
MU_VENUS = 3.24859e5
MU_EARTH = 3.986004418e5
MU_MARS = 4.282837e4
MU_JUPITER = 1.26686534e8
MU_SATURN = 3.7931187e7
MU_URANUS = 5.793939e6
MU_NEPTUNE = 6.836529e6

# Mean body radii (km)
R_MERCURY = 2439.7
R_VENUS = 6051.8
R_EARTH = 6371.0
R_MARS = 3389.5
R_JUPITER = 69911.0
R_SATURN = 58232.0
R_URANUS = 25362.0
R_NEPTUNE = 24622.0

# Minimum flyby periapsis (km) — surface + atmosphere margin
RP_MIN_MERCURY = 2600.0
RP_MIN_VENUS = 6351.0    # 300 km altitude
RP_MIN_EARTH = 6671.0    # 300 km altitude
RP_MIN_MARS = 3589.0     # 200 km altitude
RP_MIN_JUPITER = 71492.0  # cloud tops + margin
RP_MIN_SATURN = 60268.0

# NAIF body IDs
NAIF_IDS = {
    'sun': 10,
    'mercury': 1, 'mercury_barycenter': 1,
    'venus': 2, 'venus_barycenter': 2,
    'earth': 3, 'earth_barycenter': 3,
    'mars': 4, 'mars_barycenter': 4,
    'jupiter': 5, 'jupiter_barycenter': 5,
    'saturn': 6, 'saturn_barycenter': 6,
    'uranus': 7, 'uranus_barycenter': 7,
    'neptune': 8, 'neptune_barycenter': 8,
}

# Body properties lookup
BODIES = {
    'mercury': {'mu': MU_MERCURY, 'radius': R_MERCURY, 'rp_min': RP_MIN_MERCURY, 'naif_id': 1},
    'venus': {'mu': MU_VENUS, 'radius': R_VENUS, 'rp_min': RP_MIN_VENUS, 'naif_id': 2},
    'earth': {'mu': MU_EARTH, 'radius': R_EARTH, 'rp_min': RP_MIN_EARTH, 'naif_id': 3},
    'mars': {'mu': MU_MARS, 'radius': R_MARS, 'rp_min': RP_MIN_MARS, 'naif_id': 4},
    'jupiter': {'mu': MU_JUPITER, 'radius': R_JUPITER, 'rp_min': RP_MIN_JUPITER, 'naif_id': 5},
    'saturn': {'mu': MU_SATURN, 'radius': R_SATURN, 'rp_min': RP_MIN_SATURN, 'naif_id': 6},
    'uranus': {'mu': MU_URANUS, 'radius': R_URANUS, 'naif_id': 7},
    'neptune': {'mu': MU_NEPTUNE, 'radius': R_NEPTUNE, 'naif_id': 8},
}

# Path to SPICE kernels
KERNEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'kernels')
