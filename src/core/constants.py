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
MU_PLUTO = 8.71e2
MU_CERES = 6.263e1
MU_VESTA = 1.78e1
MU_ERIS = 1.108e3
MU_HAUMEA = 2.53e2
MU_MAKEMAKE = 2.0e2  # approximate

# Mean body radii (km)
R_MERCURY = 2439.7
R_VENUS = 6051.8
R_EARTH = 6371.0
R_MARS = 3389.5
R_JUPITER = 69911.0
R_SATURN = 58232.0
R_URANUS = 25362.0
R_NEPTUNE = 24622.0
R_PLUTO = 1188.3
R_CERES = 473.0
R_VESTA = 262.7
R_ERIS = 1163.0
R_HAUMEA = 816.0  # mean (ellipsoidal)
R_MAKEMAKE = 715.0

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
    'pluto': {'mu': MU_PLUTO, 'radius': R_PLUTO, 'naif_id': 9},
    'ceres': {'mu': MU_CERES, 'radius': R_CERES, 'naif_id': None},
    'vesta': {'mu': MU_VESTA, 'radius': R_VESTA, 'naif_id': None},
    'eris': {'mu': MU_ERIS, 'radius': R_ERIS, 'naif_id': None},
    'haumea': {'mu': MU_HAUMEA, 'radius': R_HAUMEA, 'naif_id': None},
    'makemake': {'mu': MU_MAKEMAKE, 'radius': R_MAKEMAKE, 'naif_id': None},
}

# Keplerian orbital elements for bodies without SPICE kernels
# Format: {a_au, e, i_deg, om_deg, w_deg, ma_deg, epoch_jd}
# Elements from JPL Small-Body Database, epoch JD 2460200.5 (2023-Sep-13)
KEPLERIAN_BODIES = {
    'uranus': {
        'a_au': 19.189, 'e': 0.0473, 'i_deg': 0.773,
        'om_deg': 74.02, 'w_deg': 96.93, 'ma_deg': 142.24,
        'epoch_jd': 2460200.5, 'period_days': 30687,
    },
    'neptune': {
        'a_au': 30.070, 'e': 0.0086, 'i_deg': 1.770,
        'om_deg': 131.78, 'w_deg': 273.19, 'ma_deg': 259.88,
        'epoch_jd': 2460200.5, 'period_days': 60190,
    },
    'pluto': {
        'a_au': 39.482, 'e': 0.2488, 'i_deg': 17.16,
        'om_deg': 110.30, 'w_deg': 113.83, 'ma_deg': 38.65,
        'epoch_jd': 2460200.5, 'period_days': 90560,
    },
    'ceres': {
        'a_au': 2.7670, 'e': 0.0785, 'i_deg': 10.587,
        'om_deg': 80.26, 'w_deg': 73.73, 'ma_deg': 60.07,
        'epoch_jd': 2460200.5, 'period_days': 1681,
    },
    'vesta': {
        'a_au': 2.3615, 'e': 0.0887, 'i_deg': 7.134,
        'om_deg': 103.81, 'w_deg': 150.73, 'ma_deg': 144.97,
        'epoch_jd': 2460200.5, 'period_days': 1325,
    },
    'eris': {
        'a_au': 67.864, 'e': 0.4407, 'i_deg': 44.04,
        'om_deg': 35.87, 'w_deg': 151.64, 'ma_deg': 205.99,
        'epoch_jd': 2460200.5, 'period_days': 204199,
    },
    'haumea': {
        'a_au': 43.218, 'e': 0.1912, 'i_deg': 28.19,
        'om_deg': 122.17, 'w_deg': 239.18, 'ma_deg': 218.45,
        'epoch_jd': 2460200.5, 'period_days': 103774,
    },
    'makemake': {
        'a_au': 45.430, 'e': 0.1613, 'i_deg': 28.98,
        'om_deg': 79.62, 'w_deg': 297.81, 'ma_deg': 165.51,
        'epoch_jd': 2460200.5, 'period_days': 111845,
    },
}

# Path to SPICE kernels
KERNEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'kernels')
