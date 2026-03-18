"""FastAPI REST server for I.C.A.R.U.S. orbital mechanics computations."""

import os
import sys
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.ephemeris import (
    load_kernels, get_body_state, get_body_position,
    utc_to_et, et_to_utc, get_states_over_range
)
from src.core.porkchop import generate_porkchop, find_optimal_transfer
from src.core.lambert import solve_lambert
from src.core.constants import MU_SUN, BODIES
from src.core.propagate import generate_trajectory_points
from src.core.cache import transfer_cache, porkchop_cache
from src.core.mga import MGATrajectory
from src.core.nea_transfer import compute_nea_transfer, generate_nea_porkchop
from src.core.low_thrust import optimize_low_thrust
from src.core.sequence_search import search_sequences
from src.data.nhats import fetch_and_cache_targets, fetch_target_details
from src.data.sbdb import fetch_asteroid_elements
from src.data.reference_missions import get_reference_missions, get_reference_mission

app = FastAPI(title="I.C.A.R.U.S. API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    load_kernels()


# --- Models ---

class PlanetState(BaseModel):
    name: str
    position: List[float]
    velocity: List[float]
    distance_au: float
    speed_kms: float

class OptimizeRequest(BaseModel):
    sequence: List[str]
    dep_start: str
    dep_end: str
    tof_bounds: List[List[float]]  # [[min_days, max_days], ...]
    v_inf_max: float = 6.0
    max_iter: int = 500
    pop_size: int = 30


# --- Endpoints ---

@app.get("/api/health")
def health():
    return {
        "status": "ok", "version": "0.2.0",
        "cache": {
            "transfer": transfer_cache.stats,
            "porkchop": porkchop_cache.stats,
        }
    }


@app.get("/api/planets/{epoch}", response_model=List[PlanetState])
def get_planet_positions(epoch: str):
    try:
        et = utc_to_et(epoch)
    except Exception as e:
        raise HTTPException(400, f"Invalid epoch: {e}")

    AU = 1.496e8
    planets = ['mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']
    result = []
    for name in planets:
        state = get_body_state(name, et)
        pos, vel = state[:3], state[3:]
        result.append(PlanetState(
            name=name, position=pos.tolist(), velocity=vel.tolist(),
            distance_au=float(np.linalg.norm(pos) / AU),
            speed_kms=float(np.linalg.norm(vel)),
        ))
    return result


@app.get("/api/planets/{body}/orbit")
def get_planet_orbit(body: str, epoch: str = '2026-01-01', points: int = 360):
    try:
        et_start = utc_to_et(epoch)
    except Exception as e:
        raise HTTPException(400, f"Invalid epoch: {e}")

    if body.lower() not in BODIES:
        raise HTTPException(404, f"Unknown body: {body}")

    periods = {
        'mercury': 88, 'venus': 225, 'earth': 365, 'mars': 687,
        'jupiter': 4333, 'saturn': 10759, 'uranus': 30687, 'neptune': 60190,
    }
    period_days = periods.get(body.lower(), 365)
    et_end = et_start + period_days * 86400

    states = get_states_over_range(body.lower(), et_start, et_end, points)
    return {
        'body': body, 'epoch': epoch, 'period_days': period_days,
        'positions': states[:, 1:4].tolist(),
    }


@app.get("/api/transfer")
def compute_transfer(departure_body: str = 'earth', arrival_body: str = 'mars',
                     departure_date: str = '2026-10-30', arrival_date: str = '2027-09-05'):
    # Check cache
    cache_key = transfer_cache.make_key(
        dep=departure_body, arr=arrival_body, dep_date=departure_date, arr_date=arrival_date
    )
    cached = transfer_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        et_dep = utc_to_et(departure_date)
        et_arr = utc_to_et(arrival_date)
    except Exception as e:
        raise HTTPException(400, f"Invalid date: {e}")

    tof = et_arr - et_dep
    if tof <= 0:
        raise HTTPException(400, "Arrival must be after departure")

    dep_state = get_body_state(departure_body.lower(), et_dep)
    arr_state = get_body_state(arrival_body.lower(), et_arr)

    try:
        v1, v2 = solve_lambert(dep_state[:3], arr_state[:3], tof, MU_SUN)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, f"Lambert solver failed: {e}")

    dv_dep = float(np.linalg.norm(v1 - dep_state[3:]))
    dv_arr = float(np.linalg.norm(v2 - arr_state[3:]))
    positions = generate_trajectory_points(dep_state[:3], v1, tof, n_points=100)

    result = {
        'departure_body': departure_body, 'arrival_body': arrival_body,
        'departure_utc': departure_date, 'arrival_utc': arrival_date,
        'tof_days': tof / 86400,
        'dv_departure': dv_dep, 'dv_arrival': dv_arr, 'dv_total': dv_dep + dv_arr,
        'c3_launch': dv_dep**2, 'v_inf_arrival': dv_arr,
        'v1_transfer': v1.tolist(), 'v2_transfer': v2.tolist(),
        'trajectory_positions': positions,
    }
    transfer_cache.set(cache_key, result)
    return result


@app.get("/api/porkchop")
def compute_porkchop(departure_body: str = 'earth', arrival_body: str = 'mars',
                     dep_start: str = '2026-08-01', dep_end: str = '2027-02-01',
                     arr_start: str = '2027-04-01', arr_end: str = '2027-12-01',
                     resolution: int = 80):
    resolution = min(resolution, 200)

    cache_key = porkchop_cache.make_key(
        dep=departure_body, arr=arrival_body,
        ds=dep_start, de=dep_end, as_=arr_start, ae=arr_end, res=resolution
    )
    cached = porkchop_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        data = generate_porkchop(
            departure_body.lower(), arrival_body.lower(),
            dep_start, dep_end, arr_start, arr_end,
            dep_steps=resolution, arr_steps=resolution,
        )
    except Exception as e:
        raise HTTPException(500, f"Porkchop generation failed: {e}")

    optimal = find_optimal_transfer(data)

    def clean_array(arr):
        result = arr.tolist()
        return [[None if (isinstance(v, float) and np.isnan(v)) else v for v in row] for row in result]

    result = {
        'departure_body': departure_body, 'arrival_body': arrival_body,
        'dep_dates': data['dep_utc'], 'arr_dates': data['arr_utc'],
        'c3_launch': clean_array(data['c3_launch']),
        'v_inf_arr': clean_array(data['v_inf_arr']),
        'dv_total': clean_array(data['dv_total']),
        'tof_days': clean_array(data['tof_days']),
        'optimal': optimal, 'resolution': resolution,
    }
    porkchop_cache.set(cache_key, result)
    return result


@app.post("/api/optimize")
def optimize_trajectory(req: OptimizeRequest):
    """Run MGA-1DSM trajectory optimization."""
    try:
        tof_bounds = [(b[0], b[1]) for b in req.tof_bounds]
        prob = MGATrajectory(
            sequence=req.sequence,
            dep_window=(req.dep_start, req.dep_end),
            tof_bounds=tof_bounds,
            v_inf_max=req.v_inf_max,
        )
        result = prob.optimize(max_iter=req.max_iter, pop_size=req.pop_size)

        # Add trajectory positions for each leg
        for leg in result.get('legs', []):
            if 'error' in leg:
                continue
            try:
                r1 = np.array(leg['r1'])
                v1 = np.array(leg['v1_transfer'])
                tof = leg['tof_days'] * 86400
                leg['trajectory_positions'] = generate_trajectory_points(r1, v1, tof, n_points=50)
            except Exception:
                leg['trajectory_positions'] = []

        return result
    except Exception as e:
        raise HTTPException(500, f"Optimization failed: {e}")


@app.get("/api/nea/transfer")
def compute_nea_transfer_endpoint(designation: str, departure_date: str, arrival_date: str):
    """Compute a Lambert transfer from Earth to a NEA using orbital elements."""
    try:
        elements = fetch_asteroid_elements(designation)
    except Exception as e:
        raise HTTPException(502, f"SBDB API error: {e}")
    if not elements:
        raise HTTPException(404, f"Asteroid '{designation}' not found")
    try:
        return compute_nea_transfer(elements, departure_date, arrival_date)
    except Exception as e:
        raise HTTPException(422, f"Transfer computation failed: {e}")


@app.get("/api/nea/porkchop")
def compute_nea_porkchop_endpoint(designation: str,
                                  dep_start: str, dep_end: str,
                                  arr_start: str, arr_end: str,
                                  resolution: int = 50):
    """Generate a porkchop plot for Earth-to-NEA transfer."""
    resolution = min(resolution, 100)
    try:
        elements = fetch_asteroid_elements(designation)
    except Exception as e:
        raise HTTPException(502, f"SBDB API error: {e}")
    if not elements:
        raise HTTPException(404, f"Asteroid '{designation}' not found")
    try:
        return generate_nea_porkchop(
            elements, dep_start, dep_end, arr_start, arr_end,
            dep_steps=resolution, arr_steps=resolution,
        )
    except Exception as e:
        raise HTTPException(500, f"NEA porkchop failed: {e}")


class LowThrustRequest(BaseModel):
    departure_body: str = 'earth'
    arrival_body: str = 'mars'
    departure_date: str = '2028-08-09'
    arrival_date: str = '2029-08-01'
    thrust_n: float = 0.1
    isp: float = 3000.0
    m0: float = 1000.0
    m_dry: float = 500.0
    n_segments: int = 20


@app.post("/api/low-thrust")
def compute_low_thrust(req: LowThrustRequest):
    """Compute a low-thrust trajectory using Sims-Flanagan method."""
    try:
        return optimize_low_thrust(
            req.departure_body, req.arrival_body,
            req.departure_date, req.arrival_date,
            thrust_n=req.thrust_n, isp=req.isp,
            m0=req.m0, m_dry=req.m_dry,
            n_segments=req.n_segments,
        )
    except Exception as e:
        raise HTTPException(500, f"Low-thrust optimization failed: {e}")


class SequenceSearchRequest(BaseModel):
    departure: str = 'earth'
    destination: str = 'saturn'
    dep_start: str = '1997-01-01'
    dep_end: str = '2000-01-01'
    max_flybys: int = 2
    quick_iter: int = 100
    quick_pop: int = 15


@app.post("/api/sequence-search")
def search_flyby_sequences(req: SequenceSearchRequest):
    """Discover optimal gravity assist sequences for a given destination."""
    try:
        return search_sequences(
            req.departure, req.destination,
            dep_window=(req.dep_start, req.dep_end),
            max_flybys=req.max_flybys,
            quick_iter=req.quick_iter,
            quick_pop=req.quick_pop,
            verbose=False,
        )
    except Exception as e:
        raise HTTPException(500, f"Sequence search failed: {e}")


@app.get("/api/reference-missions")
def list_reference_missions():
    """List all available reference missions."""
    missions = get_reference_missions()
    # Return summary without full trajectory data
    return [{
        'name': m['name'],
        'description': m['description'],
        'sequence': m['sequence'],
        'n_events': len(m['events']),
        'events': m['events'],
    } for m in missions]


@app.get("/api/reference-missions/{name}")
def get_ref_mission(name: str):
    """Get full reference mission data including trajectory positions."""
    mission = get_reference_mission(name)
    if not mission:
        raise HTTPException(404, f"Mission '{name}' not found")
    return mission


@app.get("/api/targets")
def list_targets(max_dv: int = Query(default=6, ge=4, le=12),
                 limit: int = Query(default=50, ge=1, le=500)):
    try:
        targets = fetch_and_cache_targets(max_dv=max_dv)
    except Exception as e:
        raise HTTPException(502, f"NHATS API error: {e}")
    return {'count': len(targets), 'max_dv': max_dv, 'targets': targets[:limit]}


@app.get("/api/targets/{designation}")
def get_target(designation: str):
    try:
        elements = fetch_asteroid_elements(designation)
    except Exception as e:
        raise HTTPException(502, f"SBDB API error: {e}")
    if not elements:
        raise HTTPException(404, f"Asteroid '{designation}' not found")
    return elements


if __name__ == '__main__':
    import uvicorn
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    # SPICE is not thread-safe — single-thread executor
    loop = asyncio.new_event_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
    asyncio.set_event_loop(loop)

    uvicorn.run(app, host='0.0.0.0', port=8790)
