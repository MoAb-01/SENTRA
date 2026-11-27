"""Task-safe registry of live Edge node WebSockets and Operator Console WebSockets."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionRegistry:
    """Tracks active Edge node sockets, Console operator sockets, and Core->Edge seq counters."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._edge_sockets: dict[UUID, WebSocket] = {}
        self._console_sockets: set[WebSocket] = set()
        self._server_epoch: int = int(time.time()) & 0xFFFFFFFF
        self._server_seq_by_node: dict[UUID, int] = {}
        self._confirmed_fence_version: dict[UUID, int] = {}

    async def register_edge(self, node_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._edge_sockets[node_id] = ws

    async def unregister_edge(self, node_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            if self._edge_sockets.get(node_id) is ws:
                del self._edge_sockets[node_id]

    async def register_console(self, ws: WebSocket) -> None:
        async with self._lock:
            self._console_sockets.add(ws)

    async def unregister_console(self, ws: WebSocket) -> None:
        async with self._lock:
            self._console_sockets.discard(ws)

    async def next_server_seq(self, node_id: UUID) -> tuple[int, int]:
        """Allocate a strictly monotonic (session_epoch, seq_counter) for Core->Edge frames."""
        async with self._lock:
            seq = self._server_seq_by_node.get(node_id, 0) + 1
            self._server_seq_by_node[node_id] = seq
            return self._server_epoch, seq

    async def record_fence_ack(self, node_id: UUID, version: int) -> None:
        async with self._lock:
            self._confirmed_fence_version[node_id] = version

    async def get_confirmed_fence_version(self, node_id: UUID) -> int:
        async with self._lock:
            return self._confirmed_fence_version.get(node_id, 0)

    async def is_edge_online(self, node_id: UUID) -> bool:
        async with self._lock:
            return node_id in self._edge_sockets

    async def push_to_edge(self, node_id: UUID, frame_bytes: bytes) -> bool:
        """Send a signed binary frame to an online edge node; return True if delivered."""
        async with self._lock:
            ws = self._edge_sockets.get(node_id)
        if ws is None:
            return False

        try:
            await ws.send_bytes(frame_bytes)
            return True
        except Exception as exc:
            logger.warning("Failed pushing binary frame to node=%s: %s", node_id, exc)
            await self.unregister_edge(node_id, ws)
            return False

    async def broadcast_to_consoles(self, payload: dict[str, Any]) -> int:
        """Broadcast JSON alert/telemetry event to all connected operator consoles."""
        async with self._lock:
            targets = list(self._console_sockets)
        if not targets:
            return 0

        delivered = 0
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
                delivered += 1
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._console_sockets.discard(ws)

        return delivered
