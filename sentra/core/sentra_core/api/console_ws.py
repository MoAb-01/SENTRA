"""Authenticated Operator Console live WebSocket stream (/ws/console)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from ..config import CoreConfig
from ..security import verify_access_token
from ..ws.registry import ConnectionRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["console-ws"])


def _extract_ws_jwt(ws: WebSocket) -> tuple[str | None, str | None]:
    """Extract JWT from ?token= query param or Sec-WebSocket-Protocol: sentra.v1, <jwt>."""
    query_token = ws.query_params.get("token")
    if query_token:
        return query_token, None

    proto_header = ws.headers.get("sec-websocket-protocol")
    if proto_header:
        parts = [p.strip() for p in proto_header.split(",") if p.strip()]
        if len(parts) >= 2 and parts[0] == "sentra.v1":
            return parts[1], "sentra.v1"
        if len(parts) == 1:
            return parts[0], None

    return None, None


@router.websocket("/ws/console")
async def console_websocket_endpoint(ws: WebSocket) -> None:
    """Stream real-time verified intrusion alerts and node telemetry to authenticated operators."""
    config: CoreConfig = ws.app.state.config
    registry: ConnectionRegistry = ws.app.state.registry

    token, subprotocol = _extract_ws_jwt(ws)
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing access token")
        return

    try:
        user = verify_access_token(token, jwt_secret=config.jwt_secret)
    except HTTPException:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired access token")
        return

    await ws.accept(subprotocol=subprotocol)
    await registry.register_console(ws)
    logger.info("Console WebSocket connected: user=%s role=%s", user.email, user.role)

    try:
        while True:
            # Keep socket alive and discard client keepalive pings
            await ws.receive_text()
    except WebSocketDisconnect:
        logger.info("Console WebSocket disconnected: user=%s", user.email)
    finally:
        await registry.unregister_console(ws)
