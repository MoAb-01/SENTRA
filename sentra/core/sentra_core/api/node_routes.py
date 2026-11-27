"""Edge node management and live versioned geofence synchronization routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sentra_protocol.models import VirtualFencePolygon

from ..config import CoreConfig
from ..repositories.nodes_repo import EdgeNodeRecord, NodesRepository, VirtualFenceRecord
from ..security import AuthenticatedUser, derive_node_key, require_roles
from ..ws.edge_gateway import push_fence_sync_to_node
from ..ws.registry import ConnectionRegistry

router = APIRouter(prefix="/api/v1/nodes", tags=["nodes"])


class RegisterNodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    location: str = Field(default="", max_length=256)


class UpdateFenceRequest(VirtualFencePolygon):
    """Validates 3..12 normalized non-degenerate vertices via Phase 1 VirtualFencePolygon."""

    name: str = Field(default="Primary Perimeter", min_length=1, max_length=128)
    is_active: bool = True


def _serialize_node(node: EdgeNodeRecord, active_fence: VirtualFenceRecord | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": str(node.node_id),
        "name": node.name,
        "location": node.location,
        "active_key_id": node.active_key_id,
        "last_seq_counter": node.last_seq_counter,
        "last_session_epoch": node.last_session_epoch,
        "status": node.status,
        "last_heartbeat_at": node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None,
        "created_at": node.created_at.isoformat(),
        "updated_at": node.updated_at.isoformat(),
    }
    if active_fence is not None:
        payload["active_fence"] = _serialize_fence(active_fence)
    return payload


def _serialize_fence(fence: VirtualFenceRecord) -> dict[str, object]:
    return {
        "fence_id": str(fence.fence_id),
        "node_id": str(fence.node_id),
        "name": fence.name,
        "version": fence.version,
        "vertices": [list(pt) for pt in fence.vertices],
        "is_active": fence.is_active,
        "created_by": str(fence.created_by) if fence.created_by else None,
        "created_at": fence.created_at.isoformat(),
    }


@router.get("")
async def list_nodes(
    request: Request,
    _user: AuthenticatedUser = Depends(require_roles("ADMIN", "OPERATOR", "AUDITOR")),
) -> list[dict[str, object]]:
    """List all registered edge nodes and their active geofences."""
    nodes_repo: NodesRepository = request.app.state.nodes_repo
    nodes = await nodes_repo.list_nodes()
    results: list[dict[str, object]] = []
    for node in nodes:
        fence = await nodes_repo.get_active_fence(node.node_id)
        results.append(_serialize_node(node, fence))
    return results


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_node(
    body: RegisterNodeRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_roles("ADMIN")),
) -> dict[str, object]:
    """ADMIN only: register an edge node and return its HKDF-derived provisioning key once."""
    config: CoreConfig = request.app.state.config
    nodes_repo: NodesRepository = request.app.state.nodes_repo

    node = await nodes_repo.register_node(
        name=body.name.strip(),
        location=body.location.strip(),
        actor_user_id=admin.user_id,
    )
    provisioning_key_hex = derive_node_key(
        config.node_master_key, node.node_id, node.active_key_id
    ).hex()

    return {
        "node": _serialize_node(node),
        "provisioning_key_hex": provisioning_key_hex,
    }


@router.put("/{node_id}/fence")
async def update_node_fence(
    node_id: UUID,
    body: UpdateFenceRequest,
    request: Request,
    actor: AuthenticatedUser = Depends(require_roles("ADMIN", "OPERATOR")),
) -> dict[str, object]:
    """ADMIN or OPERATOR: persist next geofence version, write audit log, and push live FENCE_SYNC."""
    config: CoreConfig = request.app.state.config
    nodes_repo: NodesRepository = request.app.state.nodes_repo
    registry: ConnectionRegistry = request.app.state.registry

    node = await nodes_repo.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge node not found")

    fence = await nodes_repo.upsert_fence_version(
        node_id=node_id,
        name=body.name.strip(),
        vertices=list(body.vertices),
        is_active=body.is_active,
        actor_user_id=actor.user_id,
    )

    pushed_live = await push_fence_sync_to_node(
        fence=fence,
        key_id=node.active_key_id,
        master_key=config.node_master_key,
        registry=registry,
    )

    return {
        "fence": _serialize_fence(fence),
        "pushed_live": pushed_live,
    }
