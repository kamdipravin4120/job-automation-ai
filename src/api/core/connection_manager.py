from __future__ import annotations

import json

from starlette.websockets import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, device_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(device_id, set()).add(ws)

    async def disconnect(self, device_id: str, ws: WebSocket) -> None:
        bucket = self._connections.get(device_id, set())
        bucket.discard(ws)
        if not bucket:
            self._connections.pop(device_id, None)

    async def send(self, device_id: str, payload: dict) -> None:
        dead = set()
        for ws in list(self._connections.get(device_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            await self.disconnect(device_id, ws)

    async def broadcast(self, payload: dict) -> None:
        for device_id in list(self._connections):
            await self.send(device_id, payload)


manager = ConnectionManager()
