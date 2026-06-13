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
        "isro_story": None,
        "alt_km": ISS_ALT_KM,
        "inclination_deg": ISS_INCLINATION_DEG,
        "waypoints": _inclined_orbit_waypoints(ISS_ALT_KM, ISS_INCLINATION_DEG),
        "agency": "NASA / Roscosmos",
    },
    "isro_eos": {
        "id": "isro_eos",
        "name": "ISRO EOS-07",
        "description": "Indian Earth Observation · 529 km · Sun-sync",
        "isro_story": "Sun-synchronous dawn-dusk orbit for ISRO Earth observation — high debris density in SSO shell.",
        "alt_km": 529,
        "inclination_deg": 97.4,
        "waypoints": _inclined_orbit_waypoints(529, 97.4),
        "agency": "ISRO",
    },
    "isro_leo": {
        "id": "isro_leo",
        "name": "ISRO LEO Comms",
        "description": "Proposed Indian LEO relay · 650 km",
        "isro_story": "Representative ISRO LEO comms relay band — assess conjunction risk before manifesting GSAT/EOS rides.",
        "alt_km": 650,
        "inclination_deg": 51.6,
        "waypoints": _inclined_orbit_waypoints(650, 51.6),
        "agency": "ISRO",
    },
    "chandrayaan_3": {
        "id": "chandrayaan_3",
        "name": "Chandrayaan-3 Parking",
        "description": "Pre-lunar injection LEO · 100 km · 32.5° inclination",
        "isro_story": (
            "Chandrayaan-3 Earth parking orbit before Trans-Lunar Injection. "
            "ISRO must verify debris clearance before the critical TLI burn from Sriharikota injection corridor."
        ),
        "alt_km": 100,
        "inclination_deg": 32.5,
        "waypoints": _inclined_orbit_waypoints(100, 32.5),
        "agency": "ISRO",
    },
    "aditya_l1": {
        "id": "aditya_l1",
        "name": "Aditya-L1 Transfer",
        "description": "Earth departure phase · 650 km · 37.6° before Sun-Earth L1",
        "isro_story": (
            "Aditya-L1 solar observatory Earth-orbit phase before halo insertion at Sun-Earth L1 (~1.5M km). "
            "Score debris risk during the LEO departure window over the Indian Ocean launch corridor."
        ),
        "alt_km": 650,
        "inclination_deg": 37.6,
        "waypoints": _inclined_orbit_waypoints(650, 37.6),
        "agency": "ISRO",
    },
}
