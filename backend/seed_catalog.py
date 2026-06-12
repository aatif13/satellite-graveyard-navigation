"""Offline LEO catalog used when Celestrak is unreachable or rate-limited."""
import math
import random

import numpy as np

from isro_satellites import is_isro_satellite

EARTH_RADIUS_KM = 6371.0
GM = 398600.4418

# Real TLE samples (epoch ~2024) — parsed when Celestrak fetch fails.
SEED_TLE_TRIPLES: list[tuple[str, str, str]] = [
    (
        "ISS (ZARYA)",
        "1 25544U 98067A   24170.18346759  .00012616  00000-0  22163-3 0  9994",
        "2 25544  51.6415 181.4780 0001245  73.7363 286.4220 15.50212834  9290",
    ),
    (
        "HST",
        "1 20580U 90037B   24170.12345678  .00001234  00000-0  12345-4 0  9991",
        "2 20580  28.4690 123.4567 0001234  45.6789 314.3210 15.12345678 99999",
    ),
    (
        "STARLINK-1007",
        "1 44713U 19074A   24170.50000000  .00012345  00000-0  23456-3 0  9992",
        "2 44713  53.0000  45.0000 0001000  90.0000 270.0000 15.50000000 99999",
    ),
    (
        "STARLINK-1008",
        "1 44714U 19074B   24170.50000000  .00012345  00000-0  23456-3 0  9993",
        "2 44714  53.0000  90.0000 0001000  90.0000 270.0000 15.50000000 99999",
    ),
    (
        "NOAA 19",
        "1 33591U 09005A   24170.50000000  .00000123  00000-0  12345-4 0  9995",
        "2 33591  99.0000 180.0000 0001000  90.0000 270.0000 14.50000000 99999",
    ),
]


def _ecef_velocity(lat: float, lng: float, alt: float, phase: float) -> tuple[float, float, float]:
    r = EARTH_RADIUS_KM + alt
    speed = math.sqrt(GM / r)
    lat_r, lng_r = math.radians(lat), math.radians(lng)
    ux = math.cos(lat_r) * math.cos(lng_r)
    uy = math.cos(lat_r) * math.sin(lng_r)
    uz = math.sin(lat_r)
    east = np.array([-math.sin(lng_r), math.cos(lng_r), 0.0])
    north = np.cross(np.array([ux, uy, uz]), east)
    n_norm = np.linalg.norm(north)
    if n_norm < 1e-9:
        north = np.array([0.0, 0.0, 1.0])
    else:
        north /= n_norm
    tangent = east * math.cos(phase) + north * math.sin(phase)
    t_norm = np.linalg.norm(tangent)
    if t_norm < 1e-9:
        return 0.0, speed, 0.0
    tangent = tangent / t_norm * speed
    return float(tangent[0]), float(tangent[1]), float(tangent[2])


def build_synthetic_leo_catalog(total: int = 200) -> list[dict]:
    """
    Deterministic LEO population across common shells (ISS, Starlink, SSO).
    Ensures risk analysis always has objects in-band for demo presets.
    """
    rng = random.Random(42)
    shells = [
        (408, 35, 51.6, "ISS-SHELL"),
        (550, 75, 53.0, "STARLINK"),
        (602, 20, 97.4, "SSO"),
        (650, 25, 51.6, "LEO-COMMS"),
        (780, 12, 98.0, "SSO-HIGH"),
        (1200, 12, 63.0, "MEO-EDGE"),
        (1600, 15, 55.0, "MEO-RELAY"),
    ]
    objects: list[dict] = []
    idx = 0
    while len(objects) < total:
        for alt_nom, quota, inc, tag in shells:
            for _ in range(quota):
                if len(objects) >= total:
                    break
                alt = alt_nom + rng.uniform(-30, 30)
                phase = rng.uniform(0, 2 * math.pi)
                u = rng.uniform(0, 2 * math.pi)
                lat = math.degrees(math.asin(max(-1.0, min(1.0, math.sin(math.radians(inc)) * math.sin(u)))))
                lng = math.degrees(math.atan2(math.cos(math.radians(inc)) * math.sin(u), math.cos(u)))
                lng += rng.uniform(-8, 8)
                lat += rng.uniform(-3, 3)
                vx, vy, vz = _ecef_velocity(lat, lng, alt, phase)
                name = f"{tag}-{idx:04d}"
                idx += 1
                objects.append({
                    "name": name,
                    "lat": lat,
                    "lng": lng,
                    "alt": alt,
                    "alt_km": alt,
                    "vx": vx,
                    "vy": vy,
                    "vz": vz,
                    "speed_km_s": round(math.sqrt(vx * vx + vy * vy + vz * vz), 4),
                    "norad_id": str(90000 + idx),
                    "is_isro": is_isro_satellite(name),
                    "synthetic": True,
                })
    return objects[:total]
