import math
import os
import pickle
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from sgp4.api import Satrec, jday

from isro_satellites import is_isro_satellite
from seed_catalog import SEED_TLE_TRIPLES, build_synthetic_leo_catalog
from space_track import fetch_space_track_catalog

EARTH_RADIUS_KM = 6371.0
USER_AGENT = "SatelliteGraveyardNavigator/1.0 (FAR-AWAY-2026)"

GP_BASE = "https://celestrak.org/NORAD/elements/gp.php"

# SATCAT endpoints are deprecated (403/timeout); gp.php is the live source.
CELESTRAK_TLE_URLS: list[str] = []

# gp.php is the live Celestrak source (10,000+ objects).
CELESTRAK_GP_GROUPS = [
    "active", "stations", "debris", "science", "weather", "gps-ops", "galileo",
    "last-30-days", "oneweb", "starlink",
]

CELESTRAK_HEAVY_GROUPS = {"starlink", "oneweb"}
CELESTRAK_EARLY_EXIT = 5000

# Outside backend/ so uvicorn --reload does not restart on cache writes
CACHE_DIR = Path(__file__).parent.parent / ".data" / "cache"
DISK_CACHE = CACHE_DIR / "debris_cache.pkl"
TLE_DISK_CACHE = CACHE_DIR / "tle_catalog.pkl"

TLE_TTL = 1800       # 30 min — re-download TLE catalog
OBJECTS_TTL = 600    # 10 min — re-propagate only
WORKERS = int(os.getenv("PROPAGATION_WORKERS", "4"))
MIN_CATALOG_OBJECTS = 50    # Partial Celestrak responses are treated as empty
MIN_TLE_TRIPLES = 500       # Do not replace a good on-disk TLE set with a tiny fetch
CELESTRAK_TARGET_OBJECTS = 400  # Below this, keep trying live Celestrak fetch

_cache: dict = {"objects": [], "fetched_at": 0.0}
_tle_catalog: list[tuple[str, str, str]] = []
_tle_fetched_at: float = 0.0
_satrec_cache: list[tuple[str, Satrec, bool]] | None = None
_refresh_lock = threading.Lock()
_refreshing = False
_refresh_callback = None
_catalog_source: str = "cache"


def set_refresh_callback(cb):
    global _refresh_callback
    _refresh_callback = cb


def get_catalog_source() -> str:
    """Origin of current TLE catalog: space-track, celestrak, seed, cache, synthetic."""
    return _catalog_source


def _norad_from_line1(l1: str) -> str:
    parts = l1.split()
    if len(parts) < 2:
        return "UNKNOWN"
    return parts[1].rstrip("U").lstrip("0") or parts[1]


def _parse_tle_lines(text: str) -> list[tuple[str, str, str]]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return []
    if lines[0].startswith("Invalid") or lines[0].startswith("GP data"):
        return []
    if lines[0].startswith("<") or "Query removed" in text:
        return []

    triples: list[tuple[str, str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 3-line TLE: name + line1 + line2
        if (
            i + 2 < len(lines)
            and lines[i + 1].startswith("1 ")
            and lines[i + 2].startswith("2 ")
            and not line.startswith("1 ")
            and not line.startswith("2 ")
        ):
            triples.append((line.lstrip("0 ").strip(), lines[i + 1], lines[i + 2]))
            i += 3
            continue

        # 2-line TLE: line1 + line2 (Space-Track GP format)
        if line.startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            l1, l2 = line, lines[i + 1]
            name = f"NORAD {_norad_from_line1(l1)}"
            if (
                i > 0
                and not lines[i - 1].startswith("1 ")
                and not lines[i - 1].startswith("2 ")
            ):
                name = lines[i - 1].lstrip("0 ").strip()
            triples.append((name, l1, l2))
            i += 2
            continue

        i += 1
    return triples


def _ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    r = math.sqrt(x * x + y * y + z * z)
    lat = math.degrees(math.asin(z / r)) if r else 0.0
    lon = math.degrees(math.atan2(y, x))
    alt = r - EARTH_RADIUS_KM
    return lat, lon, alt


def propagate_satrec_at(sat: Satrec, when: datetime) -> tuple | None:
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
    return lat, lon, alt, x, y, z, vx, vy, vz


def _fetch_one_url(
    url: str,
    seen_names: set[str],
    timeout: int = 45,
    retries: int = 4,
) -> list[tuple[str, str, str]]:
    """Fetch a single Celestrak URL with retry/backoff on 403 rate limits."""
    headers = {"User-Agent": USER_AGENT}
    batch: list[tuple[str, str, str]] = []

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            if resp.status_code == 403:
                wait = 6 * (attempt + 1)
                print(f"Celestrak 403 ({url.split('?')[-1][:30]}), retry in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            batch = _parse_tle_lines(resp.text)
            if batch:
                break
        except requests.RequestException as exc:
            if attempt == retries - 1:
                print(f"Celestrak fetch failed ({url}): {exc}")
            time.sleep(min(4 * (attempt + 1), 8))

    added: list[tuple[str, str, str]] = []
    for name, l1, l2 in batch:
        norm = name.strip().upper()
        if norm in seen_names:
            continue
        seen_names.add(norm)
        added.append((name.strip(), l1, l2))
    if added:
        print(f"Celestrak: +{len(added)} from {url.split('?')[-1][:40]}")
    time.sleep(2)
    return added


def _fetch_urls(urls: list[str], timeout: int = 45) -> list[tuple[str, str, str]]:
    seen_names: set[str] = set()
    triples: list[tuple[str, str, str]] = []
    for url in urls:
        triples.extend(_fetch_one_url(url, seen_names, timeout=timeout))
    return triples


def _fetch_celestrak_catalog() -> list[tuple[str, str, str]]:
    """Fetch TLEs from Celestrak gp.php; lighter groups first, heavy groups last."""
    seen_names: set[str] = set()
    triples: list[tuple[str, str, str]] = []

    for url in CELESTRAK_TLE_URLS:
        triples.extend(_fetch_one_url(url, seen_names, timeout=15, retries=2))

    for group in CELESTRAK_GP_GROUPS:
        url = f"{GP_BASE}?GROUP={group}&FORMAT=TLE"
        is_heavy = group in CELESTRAK_HEAVY_GROUPS
        retries = 1 if is_heavy else 2
        timeout = 18 if is_heavy else 30
        batch = _fetch_one_url(url, seen_names, timeout=timeout, retries=retries)
        if batch:
            triples.extend(batch)
            if len(triples) >= MIN_TLE_TRIPLES:
                _persist_tle_catalog(triples)
            if len(triples) >= CELESTRAK_EARLY_EXIT and not is_heavy:
                print(f"Celestrak: early exit with {len(triples)} TLEs (skipping heavy groups)")
                break

    print(f"Fetched {len(triples)} TLE triples from Celestrak")
    return triples


def _persist_tle_catalog(triples: list[tuple[str, str, str]]) -> None:
    """Save TLE progress to disk so rate-limited retries do not lose data."""
    global _tle_catalog, _tle_fetched_at, _satrec_cache
    if len(triples) < MIN_TLE_TRIPLES:
        return
    if _tle_catalog and len(triples) < len(_tle_catalog):
        return
    _tle_catalog = triples
    _tle_fetched_at = time.time()
    _satrec_cache = None
    _save_disk_cache()


def catalog_is_live(objects: list[dict] | None = None) -> bool:
    objs = objects if objects is not None else (_cache.get("objects") or [])
    if len(objs) < CELESTRAK_TARGET_OBJECTS:
        return False
    return not any(o.get("synthetic") for o in objs)


def _build_satrecs(triples: list[tuple[str, str, str]]) -> list[tuple[str, Satrec, bool]]:
    satrecs = []
    for name, l1, l2 in triples:
        try:
            sat = Satrec.twoline2rv(l1, l2)
            satrecs.append((name, sat, is_isro_satellite(name)))
        except Exception:
            continue
    return satrecs


def _propagate_one(entry: tuple[str, Satrec, bool], when: datetime) -> dict | None:
    name, sat, is_isro = entry
    result = propagate_satrec_at(sat, when)
    if not result:
        return None
    lat, lon, alt, x, y, z, vx, vy, vz = result
    speed = math.sqrt(vx * vx + vy * vy + vz * vz)
    return {
        "name": name,
        "x": x, "y": y, "z": z,
        "vx": vx, "vy": vy, "vz": vz,
        "lat": lat, "lng": lon, "alt": alt,
        "alt_km": alt,
        "speed_km_s": round(speed, 4),
        "norad_id": sat.satnum,
        "is_isro": is_isro,
    }


def _propagate_parallel(satrecs: list[tuple[str, Satrec, bool]], when: datetime) -> list[dict]:
    objects: list[dict] = []
    chunk = 800
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i in range(0, len(satrecs), chunk):
            batch = satrecs[i:i + chunk]
            futures = [pool.submit(_propagate_one, entry, when) for entry in batch]
            for fut in as_completed(futures):
                obj = fut.result()
                if obj:
                    objects.append(obj)
    return objects


def _save_disk_cache():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(DISK_CACHE, "wb") as f:
            pickle.dump({"objects": _cache["objects"], "fetched_at": _cache["fetched_at"]}, f)
        with open(TLE_DISK_CACHE, "wb") as f:
            pickle.dump({"triples": _tle_catalog, "fetched_at": _tle_fetched_at}, f)
    except Exception:
        pass


def _migrate_legacy_cache():
    """Move cache from backend/.cache if present."""
    legacy = Path(__file__).parent / ".cache"
    if not legacy.exists():
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("debris_cache.pkl", "tle_catalog.pkl"):
            src, dst = legacy / name, CACHE_DIR / name
            if src.exists() and not dst.exists():
                dst.write_bytes(src.read_bytes())
    except Exception:
        pass


def _uses_generic_norad_names(names: list[str]) -> bool:
    """True when most entries are NORAD #### placeholders from a bad TLE parse."""
    if len(names) < 20:
        return False
    sample = names[:500]
    generic = sum(1 for name in sample if str(name).startswith("NORAD "))
    return generic >= len(sample) * 0.75


def _clear_disk_cache() -> None:
    global _satrec_cache
    _satrec_cache = None
    for path in (DISK_CACHE, TLE_DISK_CACHE):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def load_disk_cache() -> bool:
    """Load cached catalog from disk for instant startup."""
    global _tle_catalog, _tle_fetched_at, _satrec_cache
    _migrate_legacy_cache()
    loaded = False
    try:
        if TLE_DISK_CACHE.exists():
            with open(TLE_DISK_CACHE, "rb") as f:
                data = pickle.load(f)
                _tle_catalog = data.get("triples", [])
                _tle_fetched_at = data.get("fetched_at", 0.0)
                loaded = bool(_tle_catalog)
        if DISK_CACHE.exists():
            with open(DISK_CACHE, "rb") as f:
                data = pickle.load(f)
                if data.get("objects"):
                    _cache["objects"] = data["objects"]
                    _cache["fetched_at"] = data.get("fetched_at", 0.0)
                    loaded = True
    except Exception:
        pass

    tle_names = [name for name, _, _ in _tle_catalog]
    obj_names = [o.get("name", "") for o in (_cache.get("objects") or [])]
    if _uses_generic_norad_names(tle_names) or _uses_generic_norad_names(obj_names):
        print("Stale NORAD-only cache detected — clearing catalog for refresh with proper names")
        _tle_catalog = []
        _tle_fetched_at = 0.0
        _cache["objects"] = []
        _cache["fetched_at"] = 0.0
        _satrec_cache = None
        _clear_disk_cache()
        loaded = False

    _satrec_cache = None
    if _cache.get("objects"):
        global _catalog_source
        _catalog_source = "cache"
    if not _cache.get("objects"):
        _activate_fallback_catalog()
    elif len(_cache.get("objects") or []) < CELESTRAK_TARGET_OBJECTS:
        _schedule_refresh(force=True)
    return loaded or bool(_cache.get("objects"))


def _activate_fallback_catalog() -> list[dict]:
    """Populate cache from seed TLEs + synthetic LEO shells when Celestrak is unavailable."""
    global _tle_catalog, _tle_fetched_at, _satrec_cache
    if len(_cache.get("objects") or []) >= MIN_CATALOG_OBJECTS:
        return _cache["objects"]

    if not _tle_catalog:
        _tle_catalog = list(SEED_TLE_TRIPLES)
        _tle_fetched_at = time.time()

    _satrec_cache = _build_satrecs(_tle_catalog)
    now = datetime.now(timezone.utc)
    objects = _propagate_parallel(_satrec_cache, now)
    objects.extend(build_synthetic_leo_catalog(200))

    if objects:
        global _catalog_source
        _cache["objects"] = objects
        _cache["fetched_at"] = time.time()
        _catalog_source = "synthetic"
        _save_disk_cache()
    return objects


def _norad_key(l1: str) -> str:
    parts = l1.split()
    if len(parts) < 2:
        return l1.strip()
    return parts[1].rstrip("U").upper()


def _merge_tle_triples(
    existing: list[tuple[str, str, str]],
    incoming: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    seen_norad: set[str] = set()
    merged: list[tuple[str, str, str]] = []

    for name, l1, l2 in existing + incoming:
        key = _norad_key(l1)
        if key in seen_norad:
            continue
        seen_norad.add(key)
        merged.append((name.strip(), l1, l2))
    return merged


def _download_tle_catalog(force: bool = False) -> list[tuple[str, str, str]]:
    global _tle_catalog, _tle_fetched_at, _satrec_cache, _catalog_source
    now = time.time()
    if not force and _tle_catalog and (now - _tle_fetched_at) < TLE_TTL:
        return _tle_catalog

    triples: list[tuple[str, str, str]] = []
    source = "seed"

    space_track = fetch_space_track_catalog()
    if space_track and len(space_track) >= MIN_TLE_TRIPLES:
        triples = space_track
        source = "space-track"
    else:
        fetched = _fetch_celestrak_catalog()
        if fetched and len(fetched) >= MIN_TLE_TRIPLES:
            triples = fetched
            source = "celestrak"
        elif fetched and _tle_catalog:
            triples = _merge_tle_triples(_tle_catalog, fetched)
            source = "celestrak"
        elif fetched:
            triples = fetched
            source = "celestrak"
        elif _tle_catalog:
            print(
                f"Celestrak unavailable — keeping disk cache "
                f"({len(_tle_catalog)} TLEs, {len(_cache.get('objects') or [])} propagated)"
            )
            return _tle_catalog
        else:
            triples = list(SEED_TLE_TRIPLES)
            source = "seed"

    if triples and (not _tle_catalog or len(triples) >= len(_tle_catalog)):
        _persist_tle_catalog(triples)
        _catalog_source = source
    return _tle_catalog or triples


def get_tle_age_seconds() -> float:
    if not _tle_fetched_at:
        return -1
    return time.time() - _tle_fetched_at


def needs_network_refresh() -> bool:
    """True when a Celestrak/Space-Track download should be attempted."""
    objects = _cache.get("objects") or []
    if not objects or not catalog_is_live(objects):
        return True
    tle_age = get_tle_age_seconds()
    return tle_age < 0 or tle_age >= TLE_TTL


def get_tle_catalog() -> list[tuple[str, str, str]]:
    if not _tle_catalog:
        load_disk_cache()
    if not _tle_catalog:
        _schedule_refresh()
    return _tle_catalog


def get_satrec_catalog() -> list[tuple[str, Satrec]]:
    global _satrec_cache
    if _satrec_cache is None:
        triples = get_tle_catalog()
        _satrec_cache = _build_satrecs(triples)
    return [(n, s) for n, s, _ in _satrec_cache]


def _refresh_catalog(force_download: bool = False) -> list[dict]:
    global _satrec_cache
    now_ts = time.time()

    if not force_download and _cache["objects"] and (now_ts - _cache["fetched_at"]) < OBJECTS_TTL:
        return _cache["objects"]

    triples = _tle_catalog
    if force_download or not triples or (now_ts - _tle_fetched_at) >= TLE_TTL:
        triples = _download_tle_catalog(force=force_download)

    if not triples:
        return _activate_fallback_catalog()

    if _satrec_cache is None or force_download:
        _satrec_cache = _build_satrecs(triples)

    now = datetime.now(timezone.utc)
    objects = _propagate_parallel(_satrec_cache, now)
    print(f"Loaded {len(objects)} objects from {_catalog_source} catalog")

    if objects and len(objects) >= MIN_CATALOG_OBJECTS:
        _cache["objects"] = objects
        _cache["fetched_at"] = now_ts
        _save_disk_cache()
        return objects
    if len(_cache.get("objects") or []) < MIN_CATALOG_OBJECTS:
        return _activate_fallback_catalog()
    return _cache["objects"]


def get_cached_objects() -> list[dict]:
    """Instant read — never blocks on network or propagation."""
    if not _cache.get("objects"):
        load_disk_cache()
    if not _cache.get("objects"):
        _activate_fallback_catalog()
    elif len(_cache["objects"]) < CELESTRAK_TARGET_OBJECTS:
        _schedule_refresh(force=True)
    return list(_cache["objects"] or [])


def is_refreshing() -> bool:
    with _refresh_lock:
        return _refreshing


def _schedule_refresh(force: bool = False):
    """Kick off background refresh if not already running."""
    with _refresh_lock:
        if _refreshing:
            return
    refresh_catalog_background(force=force)


def fetch_debris_positions(force: bool = False) -> list[dict]:
    """Always return cached data immediately; never block on Celestrak/SGP4."""
    if not _cache["objects"]:
        load_disk_cache()

    now_ts = time.time()
    stale = not _cache["objects"] or (now_ts - _cache["fetched_at"]) >= OBJECTS_TTL
    if force or stale:
        _schedule_refresh(force=force)

    return get_cached_objects()


def refresh_catalog_background(on_complete=None, force: bool = False, delay_s: float = 0):
    """Fetch + propagate in a background thread — never blocks API requests."""
    def _run():
        if delay_s > 0:
            time.sleep(delay_s)
        global _refreshing
        with _refresh_lock:
            if _refreshing:
                return
            _refreshing = True
        cb = on_complete or _refresh_callback
        try:
            _refresh_catalog(force_download=force or not _tle_catalog)
            if cb:
                cb()
        finally:
            with _refresh_lock:
                _refreshing = False

    threading.Thread(target=_run, daemon=True).start()


def get_cache_age_seconds() -> float:
    if not _cache["fetched_at"]:
        return -1
    return time.time() - _cache["fetched_at"]


def ensure_debris_for_analysis(min_objects: int = MIN_CATALOG_OBJECTS) -> tuple[list[dict], bool]:
    """
    Return debris for risk analysis. Uses cache/seed immediately so /analyze
    never blocks on Celestrak; kicks off background refresh when stale.
    """
    objects = get_cached_objects()
    if len(objects) < min_objects:
        objects = _activate_fallback_catalog()
    if len(objects) < min_objects:
        _schedule_refresh(force=True)
    return objects, len(objects) >= min_objects
