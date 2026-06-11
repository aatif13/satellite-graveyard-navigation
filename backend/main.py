import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai_planner import plan_mission
from isro_satellites import ISRO_MISSIONS, is_isro_satellite
from launch_window import recommend_launch_windows
from orbit_presets import ORBIT_PRESETS
from risk_engine import score_orbit_risk
from tle_processor import fetch_debris_positions, get_cache_age_seconds
from ws_manager import live_manager

load_dotenv()

_live_task: Optional[asyncio.Task] = None


async def _broadcast_live():
    objects = fetch_debris_positions()
    await live_manager.broadcast_debris(objects, round(get_cache_age_seconds(), 1))


async def _background_refresh():
    while True:
        try:
            fetch_debris_positions(force=True)
            await _broadcast_live()
        except Exception:
            pass
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _live_task
    fetch_debris_positions(force=True)
    _live_task = asyncio.create_task(_background_refresh())
    yield
    if _live_task:
        _live_task.cancel()


app = FastAPI(
    title="Satellite Graveyard Navigator API",
    description="3D debris risk platform for FAR AWAY 2026",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrbitAnalysisRequest(BaseModel):
    waypoints: list[dict]
    target_alt_km: Optional[float] = None


class MissionQueryRequest(BaseModel):
    query: str


def _filter_isro(objects: list[dict]) -> list[dict]:
    return [o for o in objects if o.get("is_isro") or is_isro_satellite(o.get("name", ""))]


def _normalize_waypoints(waypoints: list[dict], target_alt_km: float | None) -> list[dict]:
    if not waypoints:
        return []
    alt = target_alt_km or waypoints[0].get("alt_km", waypoints[0].get("alt", 500))
    return [{**wp, "alt_km": alt} for wp in waypoints]


def _empty_risk() -> dict:
    return {
        "risk_score": 0,
        "danger_zones": [],
        "safe_altitude": 500,
        "nearby_count": 0,
        "critical_objects": [],
        "risk_breakdown": {"density": 0, "velocity_crossing": 0, "altitude_overlap": 0},
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "cache_age_s": round(get_cache_age_seconds(), 1),
        "ws_clients": live_manager.client_count,
    }


@app.get("/api/presets")
def get_orbit_presets():
    return {"presets": list(ORBIT_PRESETS.values())}


@app.websocket("/api/ws/live")
async def websocket_live(ws: WebSocket, isro_only: bool = False):
    await live_manager.connect(ws, isro_only=isro_only)
    try:
        objects = fetch_debris_positions()
        filtered = _filter_isro(objects) if isro_only else objects
        await ws.send_json({
            "type": "connected",
            "count": len(filtered),
            "objects": filtered,
            "cache_age_s": round(get_cache_age_seconds(), 1),
        })
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "set_filter":
                await live_manager.set_filter(ws, msg.get("isro_only", False))
                objects = fetch_debris_positions()
                filtered = _filter_isro(objects) if msg.get("isro_only") else objects
                await ws.send_json({
                    "type": "debris_update",
                    "count": len(filtered),
                    "objects": filtered,
                    "cache_age_s": round(get_cache_age_seconds(), 1),
                })
            elif msg.get("type") == "refresh":
                objects = fetch_debris_positions(force=True)
                prefs = await live_manager.get_prefs(ws)
                if prefs.get("isro_only"):
                    objects = _filter_isro(objects)
                await ws.send_json({
                    "type": "debris_update",
                    "count": len(objects),
                    "objects": objects,
                    "cache_age_s": round(get_cache_age_seconds(), 1),
                })
    except WebSocketDisconnect:
        await live_manager.disconnect(ws)
    except Exception:
        await live_manager.disconnect(ws)


@app.get("/api/debris")
def get_debris(
    isro_only: bool = Query(False),
    refresh: bool = Query(False),
):
    objects = fetch_debris_positions(force=refresh)
    if isro_only:
        objects = _filter_isro(objects)
    return {
        "count": len(objects),
        "objects": objects,
        "cache_age_s": round(get_cache_age_seconds(), 1),
        "live_tracking": True,
    }


@app.get("/api/isro/constellation")
def isro_constellation():
    objects = fetch_debris_positions()
    isro_objects = _filter_isro(objects)
    return {
        "missions": ISRO_MISSIONS,
        "tracked_isro_count": len(isro_objects),
        "objects": isro_objects,
    }


@app.post("/api/analyze")
def analyze_orbit(req: OrbitAnalysisRequest):
    debris = fetch_debris_positions()
    waypoints = _normalize_waypoints(req.waypoints, req.target_alt_km)
    target_alt = waypoints[0]["alt_km"] if waypoints else (req.target_alt_km or 500)
    risk = score_orbit_risk(waypoints, debris)
    windows = recommend_launch_windows(target_alt, debris)
    return {
        **risk,
        "launch_windows": windows,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/ai/plan")
def ai_plan(req: MissionQueryRequest):
    plan = plan_mission(req.query)
    debris = fetch_debris_positions()
    waypoints = plan.get("suggested_waypoints", [])
    target_alt = plan.get("target_alt_km") or (waypoints[0].get("alt_km", 550) if waypoints else 550)
    if waypoints:
        normalized = _normalize_waypoints(waypoints, target_alt)
        risk = score_orbit_risk(normalized, debris)
        windows = recommend_launch_windows(target_alt, debris)
    else:
        risk = _empty_risk()
        windows = []
    return {"plan": plan, "risk": risk, "launch_windows": windows}


@app.get("/api/heatmap")
def heatmap_data(bins: int = Query(36, ge=12, le=72)):
    objects = fetch_debris_positions()
    from collections import defaultdict
    import math

    grid: dict = defaultdict(int)
    for obj in objects:
        lat_bin = min(bins - 1, max(0, int((obj["lat"] + 90) / 180 * bins)))
        lng_bin = min(bins - 1, max(0, int((obj["lng"] + 180) / 360 * bins)))
        alt_bin = int(obj["alt"] / 100)
        key = (lat_bin, lng_bin, alt_bin)
        grid[key] += 1

    points = []
    max_count = max(grid.values()) if grid else 1
    for (lat_b, lng_b, alt_b), count in grid.items():
        points.append({
            "lat": -90 + (lat_b + 0.5) * 180 / bins,
            "lng": -180 + (lng_b + 0.5) * 360 / bins,
            "alt_km": alt_b * 100,
            "weight": count / max_count,
            "count": count,
        })
    return {"points": points, "max_density": max_count}
