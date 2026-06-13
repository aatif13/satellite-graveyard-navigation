import math
from collections import defaultdict

import numpy as np

from isro_satellites import is_isro_satellite

EARTH_RADIUS_KM = 6371.0
GM = 398600.4418  # km^3/s^2


def _debris_alt(d: dict) -> float:
    return float(d.get("alt_km", d.get("alt", 0)))


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
    """Find lowest debris-density altitude band, preferring ±300 km from mission alt."""
    if not all_alts:
        return int(round((avoid_min + avoid_max) / 2))

    center = (avoid_min + avoid_max) / 2
    bins: dict[int, int] = defaultdict(int)
    for alt in all_alts:
        bucket = int(round(alt / 50) * 50)
        bins[bucket] += 1

    if not bins:
        return int(round(center / 50) * 50)

    def best_in_band(lo: float, hi: float, min_separation: float = 50.0) -> int | None:
        candidates = [
            (alt, count) for alt, count in bins.items()
            if lo <= alt <= hi and abs(alt - center) >= min_separation
        ]
        if not candidates:
            return None
        min_count = min(c for _, c in candidates)
        tied = [alt for alt, c in candidates if c == min_count]
        return min(tied, key=lambda a: abs(a - center))

    if center < 2000:
        upward = best_in_band(center + 50, center + 300)
        if upward is not None:
            return upward
        downward = best_in_band(center - 300, center - 50)
        if downward is not None:
            return downward
    else:
        nearby = best_in_band(center - 300, center + 300)
        if nearby is not None:
            return nearby

    for radius in (500, 800, 1200):
        result = best_in_band(center - radius, center + radius)
        if result is not None:
            return result

    if center < 2000:
        regime = [b for b in bins if 200 <= b <= 2000]
    elif center < 20000:
        regime = [b for b in bins if 2000 <= b <= 20000]
    else:
        regime = [b for b in bins if 20000 <= b <= 36000]

    if regime:
        min_count = min(bins[b] for b in regime)
        tied = [b for b in regime if bins[b] == min_count]
        return min(tied, key=lambda b: abs(b - center))

    return int(round(center / 50) * 50)


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
            "avg_alt_km": round(sum(_debris_alt(m) for m in members) / len(members), 1),
        })
    zones.sort(key=lambda z: z["count"], reverse=True)
    return zones[:8]


def _insufficient_data_result(proposed_orbit: list[dict]) -> dict:
    alt = 500
    if proposed_orbit:
        alts = [p.get("alt_km", p.get("alt", 500)) for p in proposed_orbit]
        alt = int(round(sum(alts) / len(alts)))
    return {
        "risk_score": 0,
        "danger_zones": [],
        "safe_altitude": alt,
        "nearby_count": 0,
        "critical_objects": [],
        "risk_breakdown": {"density": 0, "velocity_crossing": 0, "altitude_overlap": 0},
        "data_ready": False,
        "warning": "Orbital catalog not loaded — wait for sync or click Refresh TLE data",
    }


def score_orbit_risk(proposed_orbit: list[dict], debris: list[dict]) -> dict:
    if not proposed_orbit:
        return {"risk_score": 0, "danger_zones": [], "safe_altitude": 500, "nearby_count": 0,
                "data_ready": bool(debris)}

    if not debris:
        return _insufficient_data_result(proposed_orbit)

    orbit_alts = [p.get("alt_km", p.get("alt", 500)) for p in proposed_orbit]
    orbit_min, orbit_max = min(orbit_alts), max(orbit_alts)
    orbit_vel = _orbit_velocity_ecef(proposed_orbit)
    center = (orbit_min + orbit_max) / 2

    band_margin = max(75.0, (orbit_max - orbit_min) / 2 + 50)
    nearby = [
        d for d in debris
        if orbit_min - band_margin <= _debris_alt(d) <= orbit_max + band_margin
    ]

    all_alts = [_debris_alt(d) for d in debris]
    safe_band = find_low_density_band(all_alts, orbit_min, orbit_max)

    if not nearby:
        shell_count = len([a for a in all_alts if abs(a - center) <= 75])
        if shell_count == 0:
            return {
                "risk_score": 0,
                "danger_zones": [],
                "safe_altitude": safe_band,
                "nearby_count": 0,
                "critical_objects": [],
                "risk_breakdown": {"density": 0.0, "velocity_crossing": 0.0, "altitude_overlap": 0.0},
                "data_ready": True,
                "warning": "No tracked objects near this altitude — try a LEO band (400–800 km)",
            }
        shell_density = min(100.0, shell_count / max(len(debris), 1) * 2000)
        score = max(1, min(12, int(shell_density * 0.12)))
        return {
            "risk_score": score,
            "danger_zones": [],
            "safe_altitude": safe_band,
            "nearby_count": 0,
            "critical_objects": [],
            "risk_breakdown": {
                "density": round(shell_density * 0.3, 1),
                "velocity_crossing": round(shell_density * 0.1, 1),
                "altitude_overlap": 0.0,
            },
            "data_ready": True,
            "warning": "Mission band is clear; score reflects broader shell traffic nearby",
        }

    risk_contributions = []
    crossing_values = []
    critical_objects = []

    for d in nearby:
        debris_vel = np.array([d.get("vx", 0), d.get("vy", 0), d.get("vz", 0)])
        crossing = _velocity_crossing_factor(debris_vel, orbit_vel)
        alt_score = _altitude_proximity_score(_debris_alt(d), orbit_min, orbit_max)
        contribution = crossing * alt_score
        risk_contributions.append(contribution)
        crossing_values.append(crossing)
        if contribution > 0.55:
            critical_objects.append({
                "name": d["name"],
                "norad_id": d.get("norad_id"),
                "lat": d.get("lat"),
                "lng": d.get("lng"),
                "alt_km": round(_debris_alt(d), 1),
                "crossing_factor": round(crossing, 3),
                "is_isro": is_isro_satellite(d["name"]),
            })

    from sklearn.cluster import DBSCAN

    coords = np.array([[d["lat"], d["lng"]] for d in nearby])
    clusters = DBSCAN(eps=2.0, min_samples=3).fit(coords)
    cluster_count = len(set(clusters.labels_) - {-1})

    # Density: share of catalog in this altitude shell (normalized 0–1)
    density_factor = min(1.0, len(nearby) / max(len(debris), 1) * 25)
    avg_crossing = float(np.mean(crossing_values)) if crossing_values else 0.5
    overlap_ratio = len([c for c in risk_contributions if c > 0.3]) / max(len(nearby), 1)
    cluster_penalty = min(0.3, cluster_count * 0.05)

    raw_score = (density_factor * 40) + (avg_crossing * 45) + (cluster_penalty * 100)
    risk_score = min(100, max(1, int(raw_score)))

    # Breakdown reflects each component's weighted contribution (sums ~ risk_score)
    density_pts = round(density_factor * 40, 1)
    crossing_pts = round(avg_crossing * 45, 1)
    overlap_pts = round(overlap_ratio * cluster_penalty * 100 + overlap_ratio * 15, 1)

    return {
        "risk_score": risk_score,
        "danger_zones": extract_danger_zones(clusters, nearby),
        "safe_altitude": safe_band,
        "nearby_count": len(nearby),
        "critical_objects": sorted(critical_objects, key=lambda x: x["crossing_factor"], reverse=True)[:10],
        "risk_breakdown": {
            "density": density_pts,
            "velocity_crossing": crossing_pts,
            "altitude_overlap": round(min(100.0, overlap_pts), 1),
        },
        "data_ready": True,
    }
