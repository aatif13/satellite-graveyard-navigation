"""Space-Track.org TLE catalog (primary source when credentials are configured)."""
import os

import requests

USER_AGENT = "SatelliteGraveyardNavigator/1.0 (FAR-AWAY-2026)"
LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
# Latest GP elset per on-orbit object (newest catalog; ~20k+ objects).
GP_QUERY_URL = (
    "https://www.space-track.org/basicspacedata/query/class/gp/"
    "NORAD_CAT_ID/<100000/decay_date/null-val/epoch/%3Enow-30/"
    "orderby/norad_cat_id/format/tle"
)
GP_JSON_URL = (
    "https://www.space-track.org/basicspacedata/query/class/gp/"
    "NORAD_CAT_ID/<100000/decay_date/null-val/epoch/%3Enow-30/"
    "orderby/norad_cat_id/format/json"
)


def _credentials() -> tuple[str, str] | None:
    user = os.getenv("SPACE_TRACK_USER") or os.getenv("SPACE_TRACK_IDENTITY")
    password = os.getenv("SPACE_TRACK_PASSWORD")
    if user and password:
        return user.strip(), password.strip()
    return None


def _parse_tle_text(text: str) -> list[tuple[str, str, str]]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    triples: list[tuple[str, str, str]] = []
    for i in range(0, len(lines) - 2, 3):
        name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
        if not l1.startswith("1 ") or not l2.startswith("2 "):
            continue
        triples.append((name.strip(), l1, l2))
    return triples


def _parse_gp_json(rows: list[dict]) -> list[tuple[str, str, str]]:
    triples: list[tuple[str, str, str]] = []
    for row in rows:
        l1 = row.get("TLE_LINE1") or ""
        l2 = row.get("TLE_LINE2") or ""
        if not l1.startswith("1 ") or not l2.startswith("2 "):
            continue
        name = (row.get("OBJECT_NAME") or row.get("TLE_LINE0") or "UNKNOWN").strip()
        if name.startswith("0 "):
            name = name[2:].strip()
        triples.append((name, l1, l2))
    return triples


def fetch_space_track_catalog() -> list[tuple[str, str, str]] | None:
    """
    Download the full on-orbit GP catalog from Space-Track.org.
    Returns None when credentials are missing or login/query fails.
    """
    creds = _credentials()
    if not creds:
        return None

    user, password = creds
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        login = session.post(
            LOGIN_URL,
            data={"identity": user, "password": password},
            timeout=45,
        )
        if login.status_code != 200:
            print(f"Space-Track login failed: HTTP {login.status_code}")
            return None

        resp = session.get(GP_QUERY_URL, timeout=180)
        if resp.status_code == 401:
            print("Space-Track: unauthorized — check SPACE_TRACK_USER / SPACE_TRACK_PASSWORD")
            return None
        if resp.status_code == 429:
            print("Space-Track: rate limited (429) — will use Celestrak fallback")
            return None
        resp.raise_for_status()

        triples = _parse_tle_text(resp.text)
        if len(triples) < 500:
            json_resp = session.get(GP_JSON_URL, timeout=180)
            json_resp.raise_for_status()
            triples = _parse_gp_json(json_resp.json())

        if triples:
            print(f"Space-Track: loaded {len(triples)} TLE triples")
        else:
            print("Space-Track: empty catalog response")
        return triples or None
    except requests.RequestException as exc:
        print(f"Space-Track fetch failed: {exc}")
        return None
