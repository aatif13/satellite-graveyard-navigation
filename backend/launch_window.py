import math
import random
from datetime import datetime, timedelta, timezone

from tle_processor import get_satrec_catalog, propagate_satrec_at

MORNING_HOURS = {6, 7, 8, 9}
EVENING_HOURS = {17, 18, 19, 20}
MAX_SATRECS_FOR_WINDOWS = 400


def _altitude_flux_from_debris(
    debris: list[dict],
    target_alt_km: float,
    band_km: float = 25.0,
    alt_window_km: float = 400.0,
) -> tuple[int, float]:
    """Use propagated debris positions when satrec catalog is sparse (offline/synthetic)."""
    nearby_lons = []
    count = 0
    for d in debris:
        alt = d.get("alt_km", d.get("alt", 0))
        if abs(alt - target_alt_km) > alt_window_km:
            continue
        if abs(alt - target_alt_km) <= band_km:
            count += 1
            nearby_lons.append(d.get("lng", 0))
    if len(nearby_lons) < 2:
        spread = 0.0
    else:
        spread = max(nearby_lons) - min(nearby_lons)
        if spread > 180:
            spread = 360 - spread
    return count, spread


def _altitude_flux_at_time(
    satrecs: list[tuple[str, object]],
    when: datetime,
    target_alt_km: float,
    band_km: float = 25.0,
    alt_window_km: float = 400.0,
) -> tuple[int, float]:
    """Re-propagate TLE catalog to `when` and count objects near target altitude."""
    nearby_lons = []
    count = 0

    for _name, sat in satrecs:
        result = propagate_satrec_at(sat, when)
        if not result:
            continue
        lat, lon, alt, *_ = result
        if abs(alt - target_alt_km) > alt_window_km:
            continue
        if abs(alt - target_alt_km) <= band_km:
            count += 1
            nearby_lons.append(lon)

    if len(nearby_lons) < 2:
        spread = 0.0
    else:
        spread = max(nearby_lons) - min(nearby_lons)
        if spread > 180:
            spread = 360 - spread

    return count, spread


def _slot_geometry_modifier(hour: int, day_offset: int, spread: float) -> float:
    """Morning vs evening orbital geometry produces different congestion patterns."""
    base = 1.0 + 0.18 * math.sin(math.radians((hour + day_offset * 5) * 15))
    if hour in MORNING_HOURS:
        base *= 0.85
    elif hour in EVENING_HOURS:
        base *= 1.12
    cluster_factor = 1.0 + min(0.2, spread / 300.0)
    return base * cluster_factor


def _score_to_risk_pct(raw_score: float, min_score: float, max_score: float) -> int:
    """Map raw flux score to 20%–80% risk range."""
    if max_score <= min_score:
        return 40
    normalized = (raw_score - min_score) / (max_score - min_score)
    return max(20, min(80, int(20 + normalized * 60)))


def recommend_launch_windows(
    target_alt_km: float,
    debris: list[dict],
    days_ahead: int = 7,
) -> list[dict]:
    """Launch windows scored by SGP4 re-propagation to future UTC times."""
    now = datetime.now(timezone.utc)
    satrecs = get_satrec_catalog()
    use_debris_proxy = len(satrecs) < 50 and bool(debris)

    if not use_debris_proxy and debris:
        candidate_names = {
            d["name"] for d in debris
            if abs(d.get("alt_km", d.get("alt", 0)) - target_alt_km) <= 500
        }
        if candidate_names:
            filtered = [(n, s) for n, s in satrecs if n in candidate_names]
            if len(filtered) >= 50:
                satrecs = filtered

    if not use_debris_proxy and len(satrecs) > MAX_SATRECS_FOR_WINDOWS:
        satrecs = random.sample(satrecs, MAX_SATRECS_FOR_WINDOWS)

    slot_hours = list(range(0, 24, 3))
    all_slots: list[dict] = []

    for day_offset in range(days_ahead):
        day = now + timedelta(days=day_offset)
        for hour in slot_hours:
            t = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if use_debris_proxy:
                count, spread = _altitude_flux_from_debris(debris, target_alt_km)
            else:
                count, spread = _altitude_flux_at_time(satrecs, t, target_alt_km)
            modifier = _slot_geometry_modifier(hour, day_offset, spread)
            raw_score = count * modifier + day_offset * 1.2 + hour * 0.05
            all_slots.append({
                "date": day.strftime("%Y-%m-%d"),
                "utc_hour": hour,
                "raw_score": raw_score,
                "target_alt_km": target_alt_km,
            })

    if not all_slots:
        return []

    scores = [s["raw_score"] for s in all_slots]
    min_score, max_score = min(scores), max(scores)

    for slot in all_slots:
        slot["risk_pct"] = _score_to_risk_pct(slot["raw_score"], min_score, max_score)
        slot["label"] = (
            "OPTIMAL" if slot["risk_pct"] < 35
            else "ACCEPTABLE" if slot["risk_pct"] < 55
            else "HIGH RISK"
        )

    # Best slot per day
    by_day: dict[str, dict] = {}
    for slot in all_slots:
        key = slot["date"]
        if key not in by_day or slot["risk_pct"] < by_day[key]["risk_pct"]:
            by_day[key] = slot

    daily_best = sorted(by_day.values(), key=lambda w: w["risk_pct"])

    # Re-rank daily bests across the week for wider 20–80% spread
    day_scores = [w["raw_score"] for w in daily_best]
    d_min, d_max = min(day_scores), max(day_scores)
    for w in daily_best:
        w["risk_pct"] = _score_to_risk_pct(w["raw_score"], d_min, d_max)
        w["label"] = (
            "OPTIMAL" if w["risk_pct"] < 35
            else "ACCEPTABLE" if w["risk_pct"] < 55
            else "HIGH RISK"
        )

    return [
        {
            "date": w["date"],
            "utc_hour": w["utc_hour"],
            "risk_pct": w["risk_pct"],
            "label": w["label"],
            "target_alt_km": w["target_alt_km"],
        }
        for w in daily_best[:5]
    ]
