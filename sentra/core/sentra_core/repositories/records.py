"""Immutable domain record dataclasses shared across PostgreSQL repositories and API layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sentra_protocol.models import (
    NodeStatus,
    NormalizedBBox,
    NormalizedPoint,
    TriageStatus,
    UserRole,
)


@dataclass(frozen=True, slots=True)
class AuditLogRecord:
    """Single immutable audit_logs entry."""

    log_id: int
    actor_user_id: UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    details: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UserRecord:
    """Stored RBAC user account."""

    user_id: UUID
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshTokenRecord:
    """Stored refresh token session entry."""

    token_id: UUID
    user_id: UUID
    token_family_id: UUID
    sliding_expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class EdgeNodeRecord:
    """Registered edge node row."""

    node_id: UUID
    name: str
    location: str
    active_key_id: int
    last_seq_counter: int
    last_session_epoch: int
    status: NodeStatus
    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VirtualFenceRecord:
    """Versioned JSONB virtual fence polygon row."""

    fence_id: UUID
    node_id: UUID
    name: str
    version: int
    vertices: list[NormalizedPoint]
    is_active: bool
    created_by: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReplayCheckResult:
    """Outcome of row-locked sequence watermark check."""

    is_duplicate_event: bool
    accepted_epoch: int
    accepted_seq: int


@dataclass(frozen=True, slots=True)
class IntrusionEventRow:
    """Persisted intrusion event with SHA-256 chain-of-custody digests."""

    event_id: UUID
    node_id: UUID
    seq_counter: int
    fence_id: UUID | None
    fence_version: int
    detected_at: datetime
    received_at: datetime
    confidence: float
    bbox: NormalizedBBox
    ground_point: NormalizedPoint
    persistence_frames: int
    wide_object_key: str
    wide_sha256: str
    roi_object_key: str
    roi_sha256: str
    triage_status: TriageStatus
    expires_at: datetime

    def to_payload_dict(
        self,
        *,
        wide_presigned_url: str | None = None,
        roi_presigned_url: str | None = None,
    ) -> dict[str, object]:
        """Serialize into the canonical JSON contract shared by REST and Console WebSocket."""
        data: dict[str, object] = {
            "event_id": str(self.event_id),
            "node_id": str(self.node_id),
            "seq_counter": self.seq_counter,
            "fence_id": str(self.fence_id) if self.fence_id else None,
            "fence_version": self.fence_version,
            "detected_at": self.detected_at.isoformat(),
            "received_at": self.received_at.isoformat(),
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "ground_point": list(self.ground_point),
            "persistence_frames": self.persistence_frames,
            "wide_object_key": self.wide_object_key,
            "wide_sha256": self.wide_sha256,
            "roi_object_key": self.roi_object_key,
            "roi_sha256": self.roi_sha256,
            "triage_status": self.triage_status,
            "expires_at": self.expires_at.isoformat(),
        }
        if wide_presigned_url is not None:
            data["wide_presigned_url"] = wide_presigned_url
        if roi_presigned_url is not None:
            data["roi_presigned_url"] = roi_presigned_url
        return data


@dataclass(frozen=True, slots=True)
class ExpiredEventRef:
    """Minimal pointer to an expired event for MinIO + Postgres retention sweep."""

    event_id: UUID
    wide_object_key: str
    roi_object_key: str
