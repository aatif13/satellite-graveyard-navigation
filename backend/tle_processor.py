import math
import time
from datetime import datetime, timezone

import requests
from sgp4.api import Satrec, jday

from isro_satellites import is_isro_satellite

EARTH_RADIUS_KM = 6371.0
USER_AGENT = "SatelliteGraveyardNavigator/1.0 (FAR-AWAY-2026)"
GP_BASE = "https://celestrak.org/NORAD/elements/gp.php"

# Celestrak removed GROUP=debris; use current GP groups + named debris queries
SATELLITE_GROUPS = [
    "active",
    "last-30-days",
    "stations",
    "science",
    "weather",
    "gps-ops",
    "analyst",
]

DEBRIS_QUERIES = [
    "NAME=COSMOS 2251 DEB",
    "NAME=IRIDIUM 33 DEB",
    "SPECIAL=DECAYING",
]

_cache: dict = {"objects": [], "fetched_at": 0.0, "ttl": 600}


def _gp_url(query: str) -> str:
    return f"{GP_BASE}?{query}&FORMAT=TLE"


def _parse_tle_lines(text: str) -> list[tuple[str, str, str]]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return []
    if lines[0].startswith("Invalid") or lines[0].startswith("GP data"):
        return []
    triples = []
    for i in range(0, len(lines) - 2, 3):
        triples.append((lines[i], lines[i + 1], lines[i + 2]))
    return triples


def _ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    r = math.sqrt(x * x + y * y + z * z)
    lat = math.degrees(math.asin(z / r)) if r else 0.0
    lon = math.degrees(math.atan2(y, x))
    alt = r - EARTH_RADIUS_KM
    return lat, lon, alt


def _propagate_satellite(name: str, line1: str, line2: str, when: datetime) -> dict | None:
    try:
        sat = Satrec.twoline2rv(line1, line2)
    except Exception:
        return None

    jd, fr = jday(
        when.year, when.month, when.day,
        when.hour, when.minute, when.second + when.microsecond / 1e6,
    )
    err, pos, vel = sat.sgp4(jd, fr)
    if err != 0:
        return None

    x, y, z = pos
    vx, vy, vz = vel
    lat, lon, alt = _ecef_to_geodetic(x, y, z)
    speed = math.sqrt(vx * vx + vy * vy + vz * vz)
    norad_id = line1.split()[1].rstrip("U")

    return {
        "name": name,
        "x": x, "y": y, "z": z,
        "vx": vx, "vy": vy, "vz": vz,
        "lat": lat, "lng": lon, "alt": alt,
        "alt_km": alt,
        "speed_km_s": round(speed, 4),
        "norad_id": norad_id,
        "is_isro": is_isro_satellite(name),
    }


def _fetch_query(session: requests.Session, query: str) -> list[tuple[str, str, str]]:
    try:
        resp = session.get(_gp_url(query), timeout=45)
        resp.raise_for_status()
        return _parse_tle_lines(resp.text)
    except requests.RequestException:
        return []


def _download_tle_catalog() -> list[tuple[str, str, str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    seen: set[str] = set()
    triples: list[tuple[str, str, str]] = []

    def add_triples(batch: list[tuple[str, str, str]]):
        for name, l1, l2 in batch:
            norad = l1.split()[1].rstrip("U") if l1 else name
            if norad in seen:
                continue
            seen.add(norad)
            triples.append((name, l1, l2))

    # Primary catalog — may 403 if fetched too recently
    add_triples(_fetch_query(session, "GROUP=active"))

    for group in SATELLITE_GROUPS[1:]:
        add_triples(_fetch_query(session, f"GROUP={group}"))

    for query in DEBRIS_QUERIES:
        add_triples(_fetch_query(session, query))

    return triples


def fetch_debris_positions(force: bool = False) -> list[dict]:
    now_ts = time.time()
    if not force and _cache["objects"] and (now_ts - _cache["fetched_at"]) < _cache["ttl"]:
        return _cache["objects"]

    triples = _download_tle_catalog()
    if not triples:
        # Keep stale cache rather than returning empty on transient Celestrak failure
        if _cache["objects"]:
            return _cache["objects"]
        return []

    now = datetime.now(timezone.utc)
    objects: list[dict] = []
    for name, l1, l2 in triples:
        obj = _propagate_satellite(name, l1, l2, now)
        if obj:
            objects.append(obj)

    if objects:
        _cache["objects"] = objects
        _cache["fetched_at"] = now_ts
        return objects
    if _cache["objects"]:
        return _cache["objects"]
    return []


def get_cache_age_seconds() -> float:
    if not _cache["fetched_at"]:
        return -1
    return time.time() - _cache["fetched_at"]
