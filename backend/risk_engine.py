import math
from collections import defaultdict

import numpy as np
from sklearn.cluster import DBSCAN

from isro_satellites import is_isro_satellite

EARTH_RADIUS_KM = 6371.0
GM = 398600.4418  # km^3/s^2


def _orbit_velocity_ecef(waypoints: list[dict]) -> np.ndarray:
    """Tangent velocity in ECEF (km/s), comparable to SGP4 debris velocities."""
    if len(waypoints) < 2:
        return np.array([0.0, 7.5, 0.0])
    p0, p1 = waypoints[0], waypoints[1]
    alt = p0.get("alt_km", p0.get("alt", 500))
    r = EARTH_RADIUS_KM + alt
    speed = math.sqrt(GM / r)

    u0 = _ecef_unit(p0["lat"], p0["lng"])
    u1 = _ecef_unit(p1["lat"], p1["lng"])
    tangent = u1 - u0
    tangent = tangent - np.dot(tangent, u0) * u0
    norm = np.linalg.norm(tangent)
    if norm < 1e-9:
        tangent = np.cross(u0, np.array([0.0, 0.0, 1.0]))
        norm = np.linalg.norm(tangent)
    if norm < 1e-9:
        return np.array([0.0, speed, 0.0])
    return (tangent / norm) * speed


def _ecef_unit(lat: float, lng: float) -> np.ndarray:
    lat_r, lng_r = math.radians(lat), math.radians(lng)
    return np.array([
        math.cos(lat_r) * math.cos(lng_r),
        math.cos(lat_r) * math.sin(lng_r),
        math.sin(lat_r),
    ])


def _velocity_crossing_factor(debris_vel: np.ndarray, orbit_vel: np.ndarray) -> float:
    """Crossing debris (high relative angle) scores higher than parallel co-orbiters."""
    d_norm = np.linalg.norm(debris_vel)
    o_norm = np.linalg.norm(orbit_vel)
    if d_norm < 1e-6 or o_norm < 1e-6:
        return 0.5
    cos_angle = abs(np.dot(debris_vel / d_norm, orbit_vel / o_norm))
    # parallel ~1, crossing ~0
    crossing = 1.0 - cos_angle
    return 0.3 + 0.7 * crossing


def _altitude_proximity_score(debris_alt: float, orbit_min: float, orbit_max: float) -> float:
    center = (orbit_min + orbit_max) / 2
    half_band = max((orbit_max - orbit_min) / 2, 25)
    dist = abs(debris_alt - center)
    if dist > half_band + 50:
        return 0.0
    return max(0.0, 1.0 - dist / (half_band + 50))


def find_low_density_band(all_alts: list[float], avoid_min: float, avoid_max: float) -> int:
    if not all_alts:
        return int(avoid_min)
    center = (avoid_min + avoid_max) / 2
    # Stay in same orbital regime as the mission (LEO/MEO/GEO)
    if center < 2000:
        alt_min, alt_max = 200, 2000
    elif center < 20000:
        alt_min, alt_max = 2000, 20000
    else:
        alt_min, alt_max = 20000, 36000

    bins: dict[int, int] = defaultdict(int)
    for alt in all_alts:
        if alt_min <= alt <= alt_max:
            bucket = int(round(alt / 50) * 50)
            bins[bucket] += 1

    if not bins:
        return int(round((center + 150) / 50) * 50)

    candidates = sorted(bins.items(), key=lambda x: x[1])
    for alt, _ in candidates:
        if abs(alt - center) >= 80:
            return alt
    return int(round((avoid_max + 120) / 50) * 50)


def extract_danger_zones(clusters, nearby: list[dict]) -> list[dict]:
    labels = clusters.labels_
    zones = []
    for label in set(labels):
        if label == -1:
            continue
        members = [nearby[i] for i, lb in enumerate(labels) if lb == label]
        if not members:
            continue
        zones.append({
            "lat": sum(m["lat"] for m in members) / len(members),
            "lng": sum(m["lng"] for m in members) / len(members),
            "count": len(members),
            "avg_alt_km": round(sum(m["alt"] for m in members) / len(members), 1),
        })
    zones.sort(key=lambda z: z["count"], reverse=True)
    return zones[:8]


def score_orbit_risk(proposed_orbit: list[dict], debris: list[dict]) -> dict:
    if not proposed_orbit:
        return {"risk_score": 0, "danger_zones": [], "safe_altitude": 500, "nearby_count": 0}

    orbit_alts = [p.get("alt_km", p.get("alt", 500)) for p in proposed_orbit]
    orbit_min, orbit_max = min(orbit_alts), max(orbit_alts)
    orbit_vel = _orbit_velocity_ecef(proposed_orbit)

    nearby = [
        d for d in debris
        if orbit_min - 50 <= d["alt"] <= orbit_max + 50
    ]

    if not nearby:
        return {
            "risk_score": 5,
            "danger_zones": [],
            "safe_altitude": find_low_density_band([d["alt"] for d in debris], orbit_min, orbit_max),
            "nearby_count": 0,
            "critical_objects": [],
            "risk_breakdown": {"density": 0, "velocity_crossing": 0, "altitude_overlap": 0},
        }

    risk_contributions = []
    critical_objects = []

    for d in nearby:
        debris_vel = np.array([d.get("vx", 0), d.get("vy", 0), d.get("vz", 0)])
        crossing = _velocity_crossing_factor(debris_vel, orbit_vel)
        alt_score = _altitude_proximity_score(d["alt"], orbit_min, orbit_max)
        contribution = crossing * alt_score
        risk_contributions.append(contribution)
        if contribution > 0.55:
            critical_objects.append({
                "name": d["name"],
                "alt_km": round(d["alt"], 1),
                "crossing_factor": round(crossing, 3),
                "is_isro": is_isro_satellite(d["name"]),
            })

    coords = np.array([[d["lat"], d["lng"]] for d in nearby])
    clusters = DBSCAN(eps=2.0, min_samples=3).fit(coords)

    density_factor = min(1.0, len(nearby) / max(len(debris), 1) * 80)
    avg_crossing = float(np.mean(risk_contributions)) if risk_contributions else 0
    cluster_penalty = min(0.3, len(set(clusters.labels_) - {-1}) * 0.05)

    raw_score = (density_factor * 40) + (avg_crossing * 45) + (cluster_penalty * 100)
    risk_score = min(100, max(5, int(raw_score)))

    safe_band = find_low_density_band([d["alt"] for d in debris], orbit_min, orbit_max)

    return {
        "risk_score": risk_score,
        "danger_zones": extract_danger_zones(clusters, nearby),
        "safe_altitude": safe_band,
        "nearby_count": len(nearby),
        "critical_objects": sorted(critical_objects, key=lambda x: x["crossing_factor"], reverse=True)[:10],
        "risk_breakdown": {
            "density": round(density_factor * 100, 1),
            "velocity_crossing": round(avg_crossing * 100, 1),
            "altitude_overlap": round(len([c for c in risk_contributions if c > 0.3]) / max(len(nearby), 1) * 100, 1),
        },
    }
