"""WebSocket connection registry and binary Edge gateway."""

from .edge_gateway import router as edge_ws_router
from .registry import ConnectionRegistry

__all__ = ["ConnectionRegistry", "edge_ws_router"]
