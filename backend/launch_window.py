from datetime import datetime, timedelta, timezone

import numpy as np


def recommend_launch_windows(
    target_alt_km: float,
    debris: list[dict],
    days_ahead: int = 7,
) -> list[dict]:
    """Heuristic launch windows: lower debris flux at target altitude band."""
    now = datetime.now(timezone.utc)
    windows = []

    band = 25
    for day_offset in range(days_ahead):
        day = now + timedelta(days=day_offset)
        # Simulate diurnal debris density variation (LEO traffic patterns)
        hour_scores = []
        for hour in range(0, 24, 3):
            t = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            # Count debris near target altitude with time-of-day weighting
            nearby = [
                d for d in debris
                if abs(d["alt"] - target_alt_km) <= band
            ]
            # Orbital plane precession proxy: longitude density shifts with hour
            phase = (hour + day_offset * 4) % 24
            flux_modifier = 0.85 + 0.15 * np.sin(np.radians(phase * 15))
            score = len(nearby) * flux_modifier
            hour_scores.append((hour, score))

        best_hour, best_score = min(hour_scores, key=lambda x: x[1])
        risk_pct = min(95, max(8, int(best_score / max(len(debris), 1) * 5000)))
        windows.append({
            "date": day.strftime("%Y-%m-%d"),
            "utc_hour": best_hour,
            "risk_pct": risk_pct,
            "label": "OPTIMAL" if risk_pct < 25 else "ACCEPTABLE" if risk_pct < 50 else "HIGH RISK",
            "target_alt_km": target_alt_km,
        })

    return sorted(windows, key=lambda w: w["risk_pct"])[:5]
