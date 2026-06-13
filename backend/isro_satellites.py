"""Known ISRO / Indian space assets for constellation filtering."""
import re

ISRO_SATELLITES = {
    "CARTOSAT", "RESOURCESAT", "RISAT", "OCEANSAT", "INSAT", "GSAT", "IRNSS",
    "NAVIC", "EMISAT", "HYSIS", "MICROSAT", "ANAND", "EOS", "CMS", "IDSN",
    "CHANDRAYAAN", "MANGALYAAN", "ADITYA", "XPOSAT", "NISAR", "SPADEX",
    "GAGANYAAN", "VYOM", "STUDSAT", "JUGNU", "PRATHAM", "SWAYAM",
    "BHUVAN", "SCATSAT", "SARAL", "MEGHATROPIQUES", "KALPANA", "EDUSAT",
    "KALAMSAT", "YOUTHSAT", "TECHSAR", "IMS", "HAMSAT", "CUTE", "STEPS",
}

ISRO_MISSIONS = [
    {"name": "Chandrayaan-3", "alt_km": 100, "type": "Lunar"},
    {"name": "Aditya-L1", "alt_km": 1500000, "type": "Solar"},
    {"name": "GSAT-24", "alt_km": 35786, "type": "GEO Comms"},
    {"name": "EOS-07", "alt_km": 529, "type": "Earth Observation"},
    {"name": "RISAT-2BR2", "alt_km": 557, "type": "SAR Radar"},
    {"name": "INSAT-3DS", "alt_km": 35786, "type": "Weather GEO"},
    {"name": "NAVIC (IRNSS)", "alt_km": 36000, "type": "MEO Navigation"},
    {"name": "SPADEX", "alt_km": 400, "type": "Docking Demo"},
]


def is_isro_satellite(name: str) -> bool:
    """Match ISRO tokens as whole words (avoids false hits like EOS inside GEOS)."""
    words = re.findall(r"[A-Z0-9]+", (name or "").upper())
    return any(word in ISRO_SATELLITES for word in words)
