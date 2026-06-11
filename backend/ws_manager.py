import asyncio

from fastapi import WebSocket


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

    async def get_prefs(self, ws: WebSocket) -> dict:
        async with self._lock:
            return dict(self._connections.get(ws, {}))

    async def broadcast_debris(self, objects: list[dict], cache_age_s: float):
        async with self._lock:
            snapshot = list(self._connections.items())

        dead = []
        for ws, prefs in snapshot:
            payload = objects
            if prefs.get("isro_only"):
                from isro_satellites import is_isro_satellite
                payload = [o for o in objects if is_isro_satellite(o["name"])]

            from datetime import datetime, timezone
            message = {
                "type": "debris_update",
                "count": len(payload),
                "objects": payload,
                "cache_age_s": cache_age_s,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
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
