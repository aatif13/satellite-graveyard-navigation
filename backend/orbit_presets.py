import math

ISS_ALT_KM = 408
ISS_INCLINATION_DEG = 51.6


def _inclined_orbit_waypoints(alt_km: float, inclination_deg: float, count: int = 8) -> list[dict]:
    """Ground-track waypoints for a circular inclined orbit."""
    waypoints = []
    inc = math.radians(inclination_deg)
    for i in range(count):
        u = math.radians(i * (360 / count))
        lat = math.degrees(math.asin(max(-1, min(1, math.sin(inc) * math.sin(u)))))
        lng = math.degrees(math.atan2(math.cos(inc) * math.sin(u), math.cos(u)))
        waypoints.append({"lat": round(lat, 2), "lng": round(lng, 2), "alt_km": alt_km})
    return waypoints


ORBIT_PRESETS = {
    "iss": {
        "id": "iss",
        "name": "ISS Orbit",
        "description": "International Space Station · 408 km · 51.6° inclination",
        "alt_km": ISS_ALT_KM,
        "inclination_deg": ISS_INCLINATION_DEG,
        "waypoints": _inclined_orbit_waypoints(ISS_ALT_KM, ISS_INCLINATION_DEG),
        "agency": "NASA / Roscosmos",
    },
    "isro_eos": {
        "id": "isro_eos",
        "name": "ISRO EOS-07",
        "description": "Indian Earth Observation · 529 km · Sun-sync",
        "alt_km": 529,
        "inclination_deg": 97.4,
        "waypoints": _inclined_orbit_waypoints(529, 97.4),
        "agency": "ISRO",
    },
    "isro_leo": {
        "id": "isro_leo",
        "name": "ISRO LEO Comms",
        "description": "Proposed Indian LEO relay · 650 km",
        "alt_km": 650,
        "inclination_deg": 51.6,
        "waypoints": _inclined_orbit_waypoints(650, 51.6),
        "agency": "ISRO",
    },
}
