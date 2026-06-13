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
from tle_processor import (
    catalog_is_live,
    ensure_debris_for_analysis,
    fetch_debris_positions,
    get_cache_age_seconds,
    get_cached_objects,
    get_catalog_source,
    is_refreshing,
    load_disk_cache,
    needs_network_refresh,
    refresh_catalog_background,
    set_refresh_callback,
)
from ws_manager import live_manager, _meta_message

load_dotenv()

_live_task: Optional[asyncio.Task] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _on_catalog_ready():
    if _event_loop:
        asyncio.run_coroutine_threadsafe(_broadcast_live(), _event_loop)


async def _broadcast_live():
    objects = get_cached_objects()
    await live_manager.broadcast_debris(objects, round(get_cache_age_seconds(), 1))


async def _background_refresh():
    await asyncio.sleep(120)
    while True:
        try:
            refresh_catalog_background(
                force=needs_network_refresh(),
                on_complete=_on_catalog_ready,
            )
            await asyncio.sleep(300)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _live_task, _event_loop
    _event_loop = asyncio.get_event_loop()
    load_disk_cache()
    set_refresh_callback(_on_catalog_ready)
    cached = get_cached_objects()
    if catalog_is_live(cached):
        refresh_catalog_background(on_complete=_on_catalog_ready, force=False, delay_s=0)
    else:
        refresh_catalog_background(on_complete=_on_catalog_ready, force=True, delay_s=0)
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrbitAnalysisRequest(BaseModel):
    waypoints: list[dict]
    target_alt_km: Optional[float] = None
    debris_objects: Optional[list[dict]] = None


class MissionQueryRequest(BaseModel):
    query: str


def _filter_isro(objects: list[dict]) -> list[dict]:
    return [o for o in objects if o.get("is_isro") or is_isro_satellite(o.get("name", ""))]


def _merge_debris_catalog(*sources: list[dict] | None) -> list[dict]:
    merged: dict[str, dict] = {}
    for source in sources:
        if not source:
            continue
        for obj in source:
            key = str(obj.get("norad_id") or obj.get("name") or id(obj)).upper()
            merged[key] = obj
    return list(merged.values())


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
        "data_ready": False,
        "catalog_size": 0,
    }


def _enrich_risk_metadata(risk: dict, server_debris: list[dict]) -> dict:
    data_ready = catalog_is_live(server_debris) or (
        len(server_debris) >= 50 and not any(o.get("synthetic") for o in server_debris)
    )
    risk["data_ready"] = data_ready
    if any(o.get("synthetic") for o in server_debris):
        risk.setdefault(
            "warning",
            "Offline demo catalog — add Space-Track credentials or refresh Celestrak TLE data",
        )
    elif not data_ready and not risk.get("warning"):
        risk["warning"] = "Limited catalog data — scores may update after TLE sync completes"
    return risk


@app.get("/api/health")
def health():
    objects = get_cached_objects()
    return {
        "status": "ok",
        "cache_age_s": round(get_cache_age_seconds(), 1),
        "catalog_count": len(objects),
        "catalog_live": catalog_is_live(objects),
        "catalog_source": get_catalog_source(),
        "catalog_refreshing": is_refreshing(),
        "ws_clients": live_manager.client_count,
    }


@app.get("/api/presets")
def get_orbit_presets():
    return {"presets": list(ORBIT_PRESETS.values())}


@app.websocket("/api/ws/live")
async def websocket_live(ws: WebSocket, isro_only: bool = False):
    await live_manager.connect(ws, isro_only=isro_only)
    try:
        objects = get_cached_objects()
        if not objects:
            refresh_catalog_background(on_complete=_on_catalog_ready)
        filtered = _filter_isro(objects) if isro_only else objects
        await ws.send_json(_meta_message(
            "connected",
            len(filtered),
            round(get_cache_age_seconds(), 1),
            objects,
        ))
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "set_filter":
                await live_manager.set_filter(ws, msg.get("isro_only", False))
                objects = get_cached_objects()
                filtered = _filter_isro(objects) if msg.get("isro_only") else objects
                await ws.send_json(_meta_message(
                    "debris_update",
                    len(filtered),
                    round(get_cache_age_seconds(), 1),
                    objects,
                ))
            elif msg.get("type") == "refresh":
                refresh_catalog_background(force=True, on_complete=_on_catalog_ready)
                await ws.send_json({
                    "type": "refresh_started",
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
    """Return the full propagated catalog (10,000+ when Celestrak is reachable)."""
    objects = fetch_debris_positions(force=refresh)
    if isro_only:
        objects = _filter_isro(objects)
    return {
        "count": len(objects),
        "objects": objects,
        "cache_age_s": round(get_cache_age_seconds(), 1),
        "catalog_live": catalog_is_live(objects if not isro_only else get_cached_objects()),
        "catalog_source": get_catalog_source(),
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
    server_debris, data_ready = ensure_debris_for_analysis()
    debris = server_debris
    if len(server_debris) < 50 and req.debris_objects:
        debris = _merge_debris_catalog(req.debris_objects, server_debris)
    data_ready = catalog_is_live(server_debris) or (
        len(server_debris) >= 50 and not any(o.get("synthetic") for o in server_debris)
    )
    waypoints = _normalize_waypoints(req.waypoints, req.target_alt_km)
    target_alt = waypoints[0]["alt_km"] if waypoints else (req.target_alt_km or 500)
    risk = score_orbit_risk(waypoints, debris)
    risk["catalog_size"] = len(debris)
    risk["data_ready"] = data_ready
    if any(o.get("synthetic") for o in server_debris):
        risk.setdefault(
            "warning",
            "Offline demo catalog — add Space-Track credentials or refresh Celestrak TLE data",
        )
    elif not data_ready and not risk.get("warning"):
        risk["warning"] = "Limited catalog data — scores may update after TLE sync completes"
    windows = recommend_launch_windows(target_alt, debris) if debris else []
    return {
        **risk,
        "launch_windows": windows,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/ai/plan")
def ai_plan(req: MissionQueryRequest):
    plan = plan_mission(req.query)
    server_debris, _ = ensure_debris_for_analysis()
    waypoints = plan.get("suggested_waypoints", [])
    target_alt = plan.get("target_alt_km") or (waypoints[0].get("alt_km", 550) if waypoints else 550)
    if waypoints:
        normalized = _normalize_waypoints(waypoints, target_alt)
        risk = score_orbit_risk(normalized, server_debris)
        risk["catalog_size"] = len(server_debris)
        risk = _enrich_risk_metadata(risk, server_debris)
        windows = recommend_launch_windows(target_alt, server_debris)
    else:
        risk = _enrich_risk_metadata(_empty_risk(), server_debris)
        windows = []
    return {"plan": plan, "risk": risk, "launch_windows": windows}


@app.get("/api/heatmap")
def heatmap_data(bins: int = Query(36, ge=12, le=72)):
    objects = fetch_debris_positions()
    from collections import defaultdict

    grid: dict = defaultdict(int)
    for obj in objects:
        lat_bin = min(bins - 1, max(0, int((obj["lat"] + 90) / 180 * bins)))
        lng_bin = min(bins - 1, max(0, int((obj["lng"] + 180) / 360 * bins)))
        alt = obj.get("alt_km", obj.get("alt", 0))
        alt_bin = int(alt / 100)
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
