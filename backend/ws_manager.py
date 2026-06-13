import asyncio
from datetime import datetime, timezone

from fastapi import WebSocket

from tle_processor import catalog_is_live, get_catalog_source


def _meta_message(msg_type: str, count: int, cache_age_s: float, catalog_objects: list[dict]) -> dict:
    """Lightweight WS frame — no object arrays (fetch via HTTP /api/debris)."""
    return {
        "type": msg_type,
        "count": count,
        "cache_age_s": cache_age_s,
        "catalog_live": catalog_is_live(catalog_objects),
        "catalog_source": get_catalog_source(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class LiveDebrisManager:
    def __init__(self):
        self._connections: dict[WebSocket, dict] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, isro_only: bool = False):
        await ws.accept()
        async with self._lock:
            self._connections[ws] = {"isro_only": isro_only}

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.pop(ws, None)

    async def set_filter(self, ws: WebSocket, isro_only: bool):
        async with self._lock:
            if ws in self._connections:
                self._connections[ws]["isro_only"] = isro_only

    async def broadcast_debris(self, objects: list[dict], cache_age_s: float):
        from isro_satellites import is_isro_satellite

        async with self._lock:
            snapshot = list(self._connections.items())

        dead = []
        for ws, prefs in snapshot:
            if prefs.get("isro_only"):
                count = sum(
                    1 for o in objects
                    if o.get("is_isro") or is_isro_satellite(o.get("name", ""))
                )
            else:
                count = len(objects)
            message = _meta_message("debris_update", count, cache_age_s, objects)
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)


live_manager = LiveDebrisManager()
