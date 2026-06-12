import json
import os
import re

SYSTEM_PROMPT = """You are an orbital mission planner for ISRO and global space agencies.
Given a natural-language mission description, respond ONLY with valid JSON (no markdown):
{
  "mission_name": "short title",
  "target_alt_km": <number>,
  "inclination_deg": <number>,
  "orbit_type": "LEO|MEO|GEO|HEO",
  "rationale": "2 sentences max",
  "isro_relevance": "how this helps Indian space program",
  "suggested_waypoints": [{"lat": <num>, "lng": <num>, "alt_km": <num>}, ...at least 3]
}
Use realistic altitudes: LEO 400-800km, MEO ~20200km, GEO ~35786km.
For Indian missions prefer altitudes used by ISRO (EOS ~500km, GSAT GEO, NAVIC MEO)."""


def _fallback_plan(query: str) -> dict:
    q = query.lower()
    if "lunar" in q or "moon" in q or "chandrayaan" in q:
        alt = 650 if "650" in q or "comms" in q or "relay" in q else 100
        orbit_type = "LEO" if alt >= 400 else "HEO"
    elif "geo" in q or "comms" in q or "gsat" in q:
        alt, orbit_type = 35786, "GEO"
    elif "navic" in q or "irnss" in q:
        alt, orbit_type = 35786, "MEO"
    elif "650" in q:
        alt, orbit_type = 650, "LEO"
    else:
        alt, orbit_type = 550, "LEO"

    return {
        "mission_name": "Custom LEO Mission" if orbit_type == "LEO" else f"Mission @ {alt}km",
        "target_alt_km": alt,
        "inclination_deg": 51.6 if orbit_type == "LEO" else 0,
        "orbit_type": orbit_type,
        "rationale": f"Fallback plan for '{query}'. Altitude {alt}km selected based on keyword analysis.",
        "isro_relevance": "Supports India's growing constellation and launch cadence under IN-SPACe.",
        "suggested_waypoints": [
            {"lat": 28.5, "lng": 77.2, "alt_km": alt},
            {"lat": 0, "lng": 90, "alt_km": alt},
            {"lat": -28.5, "lng": -77.2, "alt_km": alt},
            {"lat": 0, "lng": -90, "alt_km": alt},
        ],
        "source": "fallback",
    }


def plan_mission(query: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        result = _fallback_plan(query)
        result["source"] = "fallback_no_key"
        return result

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(
            f"{SYSTEM_PROMPT}\n\nMission request: {query}",
            generation_config={"temperature": 0.3},
        )
        text = response.text.strip()
        text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.MULTILINE)
        plan = json.loads(text)
        fallback = _fallback_plan(query)
        for key in ("mission_name", "target_alt_km", "inclination_deg", "orbit_type",
                    "rationale", "isro_relevance", "suggested_waypoints"):
            if key not in plan or plan[key] is None:
                plan[key] = fallback[key]
        plan["source"] = "gemini"
        return plan
    except Exception as exc:
        result = _fallback_plan(query)
        result["source"] = f"fallback_error: {exc}"
        return result
