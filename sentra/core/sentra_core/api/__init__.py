"""REST and Console WebSocket routers for SENTRA Core."""

from .auth_routes import router as auth_router
from .console_ws import router as console_ws_router
from .event_routes import router as event_router
from .node_routes import router as node_router

__all__ = ["auth_router", "console_ws_router", "event_router", "node_router"]
