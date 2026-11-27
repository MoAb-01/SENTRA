"""Intrusion event querying, presigned evidence URLs, triage updates, and audit log routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sentra_protocol.models import TriageStatus

from ..config import CoreConfig
from ..object_store import ObjectStore
from ..repositories.audit_repo import AuditLogRecord, AuditRepository
from ..repositories.events_repo import EventsRepository
from ..security import AuthenticatedUser, require_roles
from ..ws.registry import ConnectionRegistry

router = APIRouter(prefix="/api/v1", tags=["events-and-audit"])


class UpdateTriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triage_status: Literal["ACKNOWLEDGED", "FALSE_POSITIVE", "ESCALATED"]
    note: str | None = Field(default=None, max_length=500)


def _serialize_audit(entry: AuditLogRecord) -> dict[str, object]:
    return {
        "log_id": entry.log_id,
        "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else None,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "details": entry.details,
        "created_at": entry.created_at.isoformat(),
    }


@router.get("/events")
async def list_events(
    request: Request,
    node_id: UUID | None = None,
    triage_status: TriageStatus | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _user: AuthenticatedUser = Depends(require_roles("ADMIN", "OPERATOR", "AUDITOR")),
) -> list[dict[str, object]]:
    """List paginated intrusion events with optional node, triage, and time-range filters."""
    events_repo: EventsRepository = request.app.state.events_repo
    rows = await events_repo.list_events(
        node_id=node_id,
        triage_status=triage_status,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return [r.to_payload_dict() for r in rows]


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_roles("ADMIN", "OPERATOR", "AUDITOR")),
) -> dict[str, object]:
    """Return event metadata + fresh short-lived (5-minute) presigned evidence URLs."""
    config: CoreConfig = request.app.state.config
    events_repo: EventsRepository = request.app.state.events_repo
    object_store: ObjectStore = request.app.state.object_store

    row = await events_repo.get_event(event_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intrusion event not found")

    wide_url = await object_store.generate_presigned_url(
        row.wide_object_key, expires_in_sec=config.presigned_ttl_sec
    )
    roi_url = await object_store.generate_presigned_url(
        row.roi_object_key, expires_in_sec=config.presigned_ttl_sec
    )
    return row.to_payload_dict(wide_presigned_url=wide_url, roi_presigned_url=roi_url)


@router.patch("/events/{event_id}/triage")
async def patch_event_triage(
    event_id: UUID,
    body: UpdateTriageRequest,
    request: Request,
    actor: AuthenticatedUser = Depends(require_roles("ADMIN", "OPERATOR")),
) -> dict[str, object]:
    """ADMIN or OPERATOR: update triage status atomically with immutable audit log entry."""
    events_repo: EventsRepository = request.app.state.events_repo
    registry: ConnectionRegistry = request.app.state.registry

    updated = await events_repo.update_triage_status(
        event_id=event_id,
        new_status=body.triage_status,
        actor_user_id=actor.user_id,
        note=body.note,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intrusion event not found")

    await registry.broadcast_to_consoles(
        {
            "type": "TRIAGE_UPDATED",
            "data": {
                "event_id": str(updated.event_id),
                "triage_status": updated.triage_status,
                "actor_user_id": str(actor.user_id),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
    return updated.to_payload_dict()


@router.get("/audit-logs")
async def list_audit_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _user: AuthenticatedUser = Depends(require_roles("ADMIN", "AUDITOR")),
) -> list[dict[str, object]]:
    """ADMIN or AUDITOR: read paginated immutable operator & security audit logs."""
    audit_repo: AuditRepository = request.app.state.audit_repo
    entries = await audit_repo.list_logs(limit=limit, offset=offset)
    return [_serialize_audit(e) for e in entries]
