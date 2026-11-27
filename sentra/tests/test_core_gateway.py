"""Phase 3 integration, security, durability, RBAC, and retention test suite for sentra-core."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sentra_core.config import CoreConfig, load_core_config
from sentra_core.main import CoreDependencies, create_app
from sentra_core.object_store import build_evidence_keys
from sentra_core.repositories.audit_repo import AuditLogRecord
from sentra_core.repositories.auth_repo import RefreshTokenRecord, UserRecord
from sentra_core.repositories.events_repo import ExpiredEventRef, IntrusionEventRow
from sentra_core.repositories.nodes_repo import (
    EdgeNodeRecord,
    ReplayAttackError,
    ReplayCheckResult,
    VirtualFenceRecord,
)
from sentra_core.retention import RetentionWorker
from sentra_core.security import REFRESH_COOKIE_NAME, derive_node_key, hash_password
from sentra_core.ws.registry import ConnectionRegistry
from sentra_protocol.constants import MessageType
from sentra_protocol.crypto import open_frame, seal_control_frame, seal_intrusion_event, validate_replay_watermark
from sentra_protocol.errors import ReplayError
from sentra_protocol.models import (
    EventAckPayload,
    FenceAckPayload,
    FenceSyncPayload,
    HeartbeatPayload,
    ImageFormat,
    NodeStatus,
    NormalizedBBox,
    NormalizedPoint,
    TriageStatus,
    UserRole,
)

# ---------------------------------------------------------------------------
# In-memory test doubles implementing exact Repository & ObjectStore Protocols
# ---------------------------------------------------------------------------


class InMemoryAuditRepository:
    """Append-only in-memory audit_logs test double."""

    def __init__(self) -> None:
        self.logs: list[AuditLogRecord] = []

    async def append_log(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        conn: Any = None,
    ) -> AuditLogRecord:
        record = AuditLogRecord(
            log_id=len(self.logs) + 1,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=dict(details or {}),
            created_at=datetime.now(timezone.utc),
        )
        self.logs.append(record)
        return record

    async def list_logs(self, *, limit: int = 50, offset: int = 0) -> list[AuditLogRecord]:
        ordered = list(reversed(self.logs))
        return ordered[offset : offset + limit]


class _StoredRefreshToken:
    def __init__(
        self,
        token_id: UUID,
        user_id: UUID,
        family_id: UUID,
        token_hash: str,
        sliding_expires_at: datetime,
        absolute_expires_at: datetime,
    ) -> None:
        self.token_id = token_id
        self.user_id = user_id
        self.token_family_id = family_id
        self.token_hash = token_hash
        self.sliding_expires_at = sliding_expires_at
        self.absolute_expires_at = absolute_expires_at
        self.rotated_at: datetime | None = None
        self.revoked_at: datetime | None = None
        self.revoked_reason: str | None = None


class InMemoryAuthRepository:
    """In-memory Dual-Token auth store mirroring Postgres rotation + reuse detection."""

    def __init__(self) -> None:
        self._users: dict[UUID, UserRecord] = {}
        self._tokens: dict[str, _StoredRefreshToken] = {}

    def seed_user(self, *, email: str, password: str, role: UserRole) -> UserRecord:
        now = datetime.now(timezone.utc)
        user = UserRecord(
            user_id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._users[user.user_id] = user
        return user

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        return self._users.get(user_id)

    async def issue_refresh_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        inactivity_days: int,
        absolute_days: int,
        token_family_id: UUID | None = None,
    ) -> RefreshTokenRecord:
        now = datetime.now(timezone.utc)
        token_id = uuid4()
        family_id = token_family_id or uuid4()
        abs_exp = now + timedelta(days=absolute_days)
        slide_exp = min(abs_exp, now + timedelta(days=inactivity_days))
        self._tokens[token_hash] = _StoredRefreshToken(
            token_id=token_id,
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            sliding_expires_at=slide_exp,
            absolute_expires_at=abs_exp,
        )
        return RefreshTokenRecord(
            token_id=token_id,
            user_id=user_id,
            token_family_id=family_id,
            sliding_expires_at=slide_exp,
            absolute_expires_at=abs_exp,
        )

    async def rotate_refresh_token(
        self,
        *,
        old_token_hash: str,
        new_token_hash: str,
        inactivity_days: int,
    ) -> tuple[UserRecord, RefreshTokenRecord] | None:
        now = datetime.now(timezone.utc)
        tok = self._tokens.get(old_token_hash)
        if tok is None:
            return None

        if tok.rotated_at is not None or tok.revoked_at is not None:
            for item in self._tokens.values():
                if item.token_family_id == tok.token_family_id and item.revoked_at is None:
                    item.revoked_at = now
                    item.revoked_reason = "TOKEN_REUSE_DETECTED"
            return None

        if now >= tok.sliding_expires_at or now >= tok.absolute_expires_at:
            tok.revoked_at = now
            tok.revoked_reason = "EXPIRED"
            return None

        user = self._users.get(tok.user_id)
        if user is None or not user.is_active:
            return None

        tok.rotated_at = now
        new_id = uuid4()
        slide_exp = min(tok.absolute_expires_at, now + timedelta(days=inactivity_days))
        self._tokens[new_token_hash] = _StoredRefreshToken(
            token_id=new_id,
            user_id=tok.user_id,
            family_id=tok.token_family_id,
            token_hash=new_token_hash,
            sliding_expires_at=slide_exp,
            absolute_expires_at=tok.absolute_expires_at,
        )
        return user, RefreshTokenRecord(
            token_id=new_id,
            user_id=tok.user_id,
            token_family_id=tok.token_family_id,
            sliding_expires_at=slide_exp,
            absolute_expires_at=tok.absolute_expires_at,
        )

    async def revoke_token_by_hash(self, token_hash: str, reason: str = "USER_LOGOUT") -> bool:
        tok = self._tokens.get(token_hash)
        if tok is None or tok.revoked_at is not None:
            return False
        tok.revoked_at = datetime.now(timezone.utc)
        tok.revoked_reason = reason
        return True

    async def revoke_all_user_tokens(self, user_id: UUID, reason: str = "ADMIN_REVOCATION") -> int:
        now = datetime.now(timezone.utc)
        count = 0
        for tok in self._tokens.values():
            if tok.user_id == user_id and tok.revoked_at is None:
                tok.revoked_at = now
                tok.revoked_reason = reason
                count += 1
        return count


class InMemoryObjectStore:
    """In-memory private S3/MinIO vault tracking exact call order for durability assertions."""

    def __init__(self, timeline: list[str]) -> None:
        self._timeline = timeline
        self.objects: dict[str, bytes] = {}
        self.put_count: int = 0
        self.fail_next_put: bool = False
        self.fail_delete_keys: set[str] = set()

    async def ensure_bucket(self) -> None:
        return None

    async def put_evidence(
        self,
        *,
        object_key: str,
        data: bytes,
        image_format: ImageFormat = "jpeg",
    ) -> None:
        self._timeline.append(f"s3:put:{object_key}")
        if self.fail_next_put:
            self.fail_next_put = False
            raise RuntimeError("Simulated MinIO outage")
        self.objects[object_key] = data
        self.put_count += 1

    async def generate_presigned_url(
        self,
        object_key: str,
        *,
        expires_in_sec: int = 300,
    ) -> str:
        return f"https://minio.local/sentra-evidence/{object_key}?X-Amz-Expires={expires_in_sec}"

    async def delete_objects(self, object_keys: Sequence[str]) -> list[str]:
        self._timeline.append(f"s3:delete:{len(object_keys)}")
        deleted: list[str] = []
        for key in object_keys:
            if key in self.fail_delete_keys:
                continue
            self.objects.pop(key, None)
            deleted.append(key)
        return deleted


class InMemoryNodesRepository:
    """In-memory edge_nodes and virtual_fences store with replay watermark semantics."""

    def __init__(self, audit_repo: InMemoryAuditRepository) -> None:
        self._audit = audit_repo
        self.nodes: dict[UUID, EdgeNodeRecord] = {}
        self.fences: dict[UUID, list[VirtualFenceRecord]] = {}
        self._events_ref: dict[UUID, IntrusionEventRow] | None = None

    def attach_events_store(self, events: dict[UUID, IntrusionEventRow]) -> None:
        self._events_ref = events

    async def get_node(self, node_id: UUID) -> EdgeNodeRecord | None:
        return self.nodes.get(node_id)

    async def list_nodes(self) -> list[EdgeNodeRecord]:
        return list(self.nodes.values())

    async def register_node(
        self, *, name: str, location: str, actor_user_id: UUID
    ) -> EdgeNodeRecord:
        now = datetime.now(timezone.utc)
        node = EdgeNodeRecord(
            node_id=uuid4(),
            name=name,
            location=location,
            active_key_id=1,
            last_seq_counter=0,
            last_session_epoch=0,
            status="OFFLINE",
            last_heartbeat_at=None,
            created_at=now,
            updated_at=now,
        )
        self.nodes[node.node_id] = node
        await self._audit.append_log(
            actor_user_id=actor_user_id,
            action="NODE_REGISTERED",
            target_type="edge_node",
            target_id=str(node.node_id),
            details={"name": name, "location": location, "active_key_id": 1},
        )
        return node

    async def check_replay_for_event(
        self, *, node_id: UUID, session_epoch: int, seq_counter: int, event_id: UUID
    ) -> ReplayCheckResult:
        node = self.nodes.get(node_id)
        if node is None or node.status == "REVOKED":
            raise ReplayAttackError(f"Node {node_id} is unregistered or revoked")

        known_dup = bool(
            self._events_ref is not None
            and event_id in self._events_ref
            and self._events_ref[event_id].node_id == node_id
        )
        try:
            is_fresh = validate_replay_watermark(
                incoming_epoch=session_epoch,
                incoming_seq=seq_counter,
                last_epoch=node.last_session_epoch,
                last_seq=node.last_seq_counter,
                is_known_duplicate_event=known_dup,
            )
        except ReplayError as exc:
            raise ReplayAttackError(str(exc)) from exc

        return ReplayCheckResult(
            is_duplicate_event=not is_fresh,
            accepted_epoch=session_epoch,
            accepted_seq=seq_counter,
        )

    def advance_watermark_sync(self, node_id: UUID, session_epoch: int, seq_counter: int) -> None:
        node = self.nodes[node_id]
        new_epoch = max(node.last_session_epoch, session_epoch)
        new_seq = (
            seq_counter
            if session_epoch > node.last_session_epoch
            else max(node.last_seq_counter, seq_counter)
        )
        now = datetime.now(timezone.utc)
        self.nodes[node_id] = replace(
            node,
            last_session_epoch=new_epoch,
            last_seq_counter=new_seq,
            status="ONLINE",
            last_heartbeat_at=now,
            updated_at=now,
        )

    async def update_heartbeat(self, *, node_id: UUID, status: NodeStatus = "ONLINE") -> None:
        node = self.nodes.get(node_id)
        if node is not None and node.status != "REVOKED":
            now = datetime.now(timezone.utc)
            self.nodes[node_id] = replace(
                node, status=status, last_heartbeat_at=now, updated_at=now
            )

    async def get_active_fence(self, node_id: UUID) -> VirtualFenceRecord | None:
        active = [f for f in self.fences.get(node_id, []) if f.is_active]
        return max(active, key=lambda f: f.version) if active else None

    async def upsert_fence_version(
        self,
        *,
        node_id: UUID,
        name: str,
        vertices: list[NormalizedPoint],
        is_active: bool,
        actor_user_id: UUID,
    ) -> VirtualFenceRecord:
        existing = self.fences.setdefault(node_id, [])
        next_ver = max((f.version for f in existing), default=0) + 1
        self.fences[node_id] = [replace(f, is_active=False) for f in existing]
        record = VirtualFenceRecord(
            fence_id=uuid4(),
            node_id=node_id,
            name=name,
            version=next_ver,
            vertices=list(vertices),
            is_active=is_active,
            created_by=actor_user_id,
            created_at=datetime.now(timezone.utc),
        )
        self.fences[node_id].append(record)
        await self._audit.append_log(
            actor_user_id=actor_user_id,
            action="FENCE_UPDATED",
            target_type="virtual_fence",
            target_id=str(record.fence_id),
            details={"node_id": str(node_id), "version": next_ver, "vertex_count": len(vertices)},
        )
        return record


class InMemoryEventsRepository:
    """In-memory intrusion_events store tracking exact call ordering for durability checks."""

    def __init__(
        self,
        nodes_repo: InMemoryNodesRepository,
        audit_repo: InMemoryAuditRepository,
        timeline: list[str],
    ) -> None:
        self._nodes = nodes_repo
        self._audit = audit_repo
        self._timeline = timeline
        self.events: dict[UUID, IntrusionEventRow] = {}
        nodes_repo.attach_events_store(self.events)

    async def insert_event_idempotent(
        self,
        *,
        event_id: UUID,
        node_id: UUID,
        session_epoch: int,
        seq_counter: int,
        fence_id: UUID | None,
        fence_version: int,
        detected_at: datetime,
        confidence: float,
        bbox: NormalizedBBox,
        ground_point: NormalizedPoint,
        persistence_frames: int,
        wide_object_key: str,
        wide_sha256: str,
        roi_object_key: str,
        roi_sha256: str,
        expires_at: datetime,
    ) -> tuple[IntrusionEventRow, bool]:
        self._timeline.append(f"db:insert:{event_id}")
        if event_id in self.events:
            return self.events[event_id], False

        row = IntrusionEventRow(
            event_id=event_id,
            node_id=node_id,
            seq_counter=seq_counter,
            fence_id=fence_id,
            fence_version=fence_version,
            detected_at=detected_at,
            received_at=datetime.now(timezone.utc),
            confidence=confidence,
            bbox=bbox,
            ground_point=ground_point,
            persistence_frames=persistence_frames,
            wide_object_key=wide_object_key,
            wide_sha256=wide_sha256,
            roi_object_key=roi_object_key,
            roi_sha256=roi_sha256,
            triage_status="NEW",
            expires_at=expires_at,
        )
        self.events[event_id] = row
        self._nodes.advance_watermark_sync(node_id, session_epoch, seq_counter)
        return row, True

    async def get_event(self, event_id: UUID) -> IntrusionEventRow | None:
        return self.events.get(event_id)

    async def list_events(
        self,
        *,
        node_id: UUID | None = None,
        triage_status: TriageStatus | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IntrusionEventRow]:
        items = list(self.events.values())
        if node_id is not None:
            items = [e for e in items if e.node_id == node_id]
        if triage_status is not None:
            items = [e for e in items if e.triage_status == triage_status]
        if since is not None:
            items = [e for e in items if e.detected_at >= since]
        if until is not None:
            items = [e for e in items if e.detected_at <= until]
        items.sort(key=lambda e: e.received_at, reverse=True)
        return items[offset : offset + limit]

    async def update_triage_status(
        self,
        *,
        event_id: UUID,
        new_status: TriageStatus,
        actor_user_id: UUID,
        note: str | None = None,
    ) -> IntrusionEventRow | None:
        existing = self.events.get(event_id)
        if existing is None:
            return None
        updated = replace(existing, triage_status=new_status)
        self.events[event_id] = updated
        await self._audit.append_log(
            actor_user_id=actor_user_id,
            action="TRIAGE_UPDATED",
            target_type="intrusion_event",
            target_id=str(event_id),
            details={"triage_status": new_status, "note": note},
        )
        return updated

    async def fetch_expired_events(
        self, *, now: datetime, limit: int = 100
    ) -> list[ExpiredEventRef]:
        expired = sorted(
            (e for e in self.events.values() if e.expires_at <= now),
            key=lambda e: e.expires_at,
        )[:limit]
        return [
            ExpiredEventRef(
                event_id=e.event_id,
                wide_object_key=e.wide_object_key,
                roi_object_key=e.roi_object_key,
            )
            for e in expired
        ]

    async def delete_events_by_ids(self, event_ids: Sequence[UUID]) -> int:
        self._timeline.append(f"db:delete:{len(event_ids)}")
        removed = 0
        for eid in event_ids:
            if self.events.pop(eid, None) is not None:
                removed += 1
        return removed


# ---------------------------------------------------------------------------
# Test harness fixture
# ---------------------------------------------------------------------------


class GatewayHarness:
    """Bundles FastAPI app, seeded RBAC users, in-memory repositories, and operation log."""

    def __init__(self) -> None:
        self.timeline: list[str] = []
        self.config = CoreConfig(
            postgres_dsn="postgresql://sentra:test@localhost:5432/sentra",
            minio_endpoint="localhost:9000",
            minio_access_key="test-access",
            minio_secret_key="test-secret",
            minio_bucket="sentra-evidence",
            minio_secure=False,
            presigned_ttl_sec=300,
            jwt_secret_hex="a1" * 32,
            access_token_expire_minutes=15,
            refresh_token_expire_days=14,
            refresh_inactivity_days=7,
            cookie_secure=False,  # TestClient runs over http://testserver
            node_master_key_hex="b2" * 32,
            evidence_retention_days=30,
            retention_sweep_interval_sec=3600,
            cors_origins=["http://localhost:5173"],
        )
        self.audit_repo = InMemoryAuditRepository()
        self.auth_repo = InMemoryAuthRepository()
        self.nodes_repo = InMemoryNodesRepository(self.audit_repo)
        self.events_repo = InMemoryEventsRepository(self.nodes_repo, self.audit_repo, self.timeline)
        self.object_store = InMemoryObjectStore(self.timeline)
        self.registry = ConnectionRegistry()
        self.retention_worker = RetentionWorker(
            events_repo=self.events_repo,
            audit_repo=self.audit_repo,
            object_store=self.object_store,
            sweep_interval_sec=3600,
        )

        self.admin = self.auth_repo.seed_user(
            email="admin@sentra.local", password="AdminPassword!1", role="ADMIN"
        )
        self.operator = self.auth_repo.seed_user(
            email="operator@sentra.local", password="OperatorPassword!1", role="OPERATOR"
        )
        self.auditor = self.auth_repo.seed_user(
            email="auditor@sentra.local", password="AuditorPassword!1", role="AUDITOR"
        )

        deps = CoreDependencies(
            config=self.config,
            auth_repo=self.auth_repo,
            nodes_repo=self.nodes_repo,
            events_repo=self.events_repo,
            audit_repo=self.audit_repo,
            object_store=self.object_store,
            registry=self.registry,
            retention_worker=self.retention_worker,
        )
        self.app = create_app(deps_override=deps)


@pytest.fixture()
def harness() -> GatewayHarness:
    return GatewayHarness()


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_node(client: TestClient, admin_token: str, name: str = "Gate-01") -> tuple[UUID, bytes]:
    resp = client.post(
        "/api/v1/nodes",
        json={"name": name, "location": "North Perimeter"},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    node_id = UUID(body["node"]["node_id"])
    node_key = bytes.fromhex(body["provisioning_key_hex"])
    assert len(node_key) == 32
    return node_id, node_key


def _make_intrusion_frame(
    *,
    node_id: UUID,
    node_key: bytes,
    seq_counter: int,
    session_epoch: int = 100,
    event_id: UUID | None = None,
    fence_id: UUID | None = None,
    wide_bytes: bytes = b"\xff\xd8\xff\xe0WIDE_JPEG_PAYLOAD",
    roi_bytes: bytes = b"\xff\xd8\xff\xe0ROI_HEAD_TORSO_PAYLOAD",
) -> tuple[UUID, bytes, bytes, bytes]:
    eid = event_id or uuid4()
    fid = fence_id or uuid4()
    frame = seal_intrusion_event(
        node_id=node_id,
        key_id=1,
        session_epoch=session_epoch,
        seq_counter=seq_counter,
        key=node_key,
        event_id=eid,
        fence_id=fid,
        fence_version=1,
        confidence=0.92,
        bbox=(0.25, 0.20, 0.20, 0.50),
        ground_point=(0.35, 0.70),
        persistence_frames=4,
        wide_bytes=wide_bytes,
        roi_bytes=roi_bytes,
        image_format="jpeg",
        timestamp_ns=time.time_ns(),
    )
    return eid, frame, wide_bytes, roi_bytes


# ---------------------------------------------------------------------------
# 1. End-to-End Edge -> Gateway Ingestion, MinIO-First Durability & Console Push
# ---------------------------------------------------------------------------


def test_e2e_edge_ingestion_durability_and_console_broadcast(harness: GatewayHarness) -> None:
    with TestClient(harness.app) as client:
        admin_token = _login(client, "admin@sentra.local", "AdminPassword!1")
        op_token = _login(client, "operator@sentra.local", "OperatorPassword!1")
        node_id, node_key = _register_node(client, admin_token)

        assert node_key == derive_node_key(harness.config.node_master_key, node_id, 1)

        with (
            client.websocket_connect(f"/ws/console?token={op_token}") as console_ws,
            client.websocket_connect(f"/ws/edge/{node_id}") as edge_ws,
        ):
            event_id, wire_frame, wide_bytes, roi_bytes = _make_intrusion_frame(
                node_id=node_id, node_key=node_key, seq_counter=1
            )
            edge_ws.send_bytes(wire_frame)

            # Edge must receive signed EVENT_ACK(ACCEPTED)
            ack_raw = edge_ws.receive_bytes()
            ack_frame = open_frame(ack_raw, lambda nid, kid: node_key)
            assert ack_frame.header.msg_type is MessageType.EVENT_ACK
            assert isinstance(ack_frame.payload, EventAckPayload)
            assert ack_frame.payload.event_id == event_id
            assert ack_frame.payload.seq_counter == 1
            assert ack_frame.payload.status == "ACCEPTED"

            # Connected console must receive live INTRUSION_ALERT with presigned URLs
            console_msg = console_ws.receive_json()
            assert console_msg["type"] == "INTRUSION_ALERT"
            data = console_msg["data"]
            assert data["event_id"] == str(event_id)
            assert data["node_id"] == str(node_id)
            assert data["triage_status"] == "NEW"
            assert data["wide_sha256"] == hashlib.sha256(wide_bytes).hexdigest()
            assert data["roi_sha256"] == hashlib.sha256(roi_bytes).hexdigest()
            assert "X-Amz-Expires=300" in data["wide_presigned_url"]
            assert "X-Amz-Expires=300" in data["roi_presigned_url"]

        # Crash-safe ordering: BOTH MinIO puts MUST precede PostgreSQL insert
        assert len(harness.timeline) == 3
        assert harness.timeline[0].startswith("s3:put:")
        assert harness.timeline[1].startswith("s3:put:")
        assert harness.timeline[2] == f"db:insert:{event_id}"

        # Stored objects match raw decrypted crops byte-for-byte
        stored_row = harness.events_repo.events[event_id]
        assert harness.object_store.objects[stored_row.wide_object_key] == wide_bytes
        assert harness.object_store.objects[stored_row.roi_object_key] == roi_bytes


def test_no_ack_and_no_db_write_when_object_store_fails(harness: GatewayHarness) -> None:
    with TestClient(harness.app) as client:
        admin_token = _login(client, "admin@sentra.local", "AdminPassword!1")
        node_id, node_key = _register_node(client, admin_token)
        harness.object_store.fail_next_put = True

        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/edge/{node_id}") as edge_ws:
                _, wire_frame, _, _ = _make_intrusion_frame(
                    node_id=node_id, node_key=node_key, seq_counter=1
                )
                edge_ws.send_bytes(wire_frame)
                edge_ws.receive_bytes()

        assert len(harness.events_repo.events) == 0
        assert not any(step.startswith("db:insert:") for step in harness.timeline)


# ---------------------------------------------------------------------------
# 2. Idempotency & Monotonic Replay Defense
# ---------------------------------------------------------------------------


def test_idempotent_duplicate_retry_and_replay_attack_rejection(harness: GatewayHarness) -> None:
    with TestClient(harness.app) as client:
        admin_token = _login(client, "admin@sentra.local", "AdminPassword!1")
        node_id, node_key = _register_node(client, admin_token)

        with client.websocket_connect(f"/ws/edge/{node_id}") as edge_ws:
            # First delivery -> ACCEPTED
            event_id, frame1, _, _ = _make_intrusion_frame(
                node_id=node_id, node_key=node_key, seq_counter=1
            )
            edge_ws.send_bytes(frame1)
            ack1 = open_frame(edge_ws.receive_bytes(), lambda _n, _k: node_key).payload
            assert isinstance(ack1, EventAckPayload)
            assert ack1.status == "ACCEPTED"
            assert harness.object_store.put_count == 2
            assert len(harness.events_repo.events) == 1

            # Retry exact same event_id + seq_counter (dropped ACK simulation) -> DUPLICATE, no re-upload
            edge_ws.send_bytes(frame1)
            ack2 = open_frame(edge_ws.receive_bytes(), lambda _n, _k: node_key).payload
            assert isinstance(ack2, EventAckPayload)
            assert ack2.event_id == event_id
            assert ack2.status == "DUPLICATE"
            assert harness.object_store.put_count == 2
            assert len(harness.events_repo.events) == 1

            # Replay attack: same/older seq_counter=1 with a DIFFERENT event_id -> 1008 + audit log
            replay_eid, replay_frame, _, _ = _make_intrusion_frame(
                node_id=node_id, node_key=node_key, seq_counter=1
            )
            assert replay_eid != event_id
            edge_ws.send_bytes(replay_frame)
            with pytest.raises(WebSocketDisconnect) as exc_info:
                edge_ws.receive_bytes()
            assert exc_info.value.code == 1008

        assert len(harness.events_repo.events) == 1
        violations = [log for log in harness.audit_repo.logs if log.action == "EDGE_SECURITY_VIOLATION"]
        assert len(violations) == 1
        assert violations[0].details["error_type"] == "ReplayAttackError"


# ---------------------------------------------------------------------------
# 3. Tampered AAD, Tampered Ciphertext & Cross-Node Spoofing Rejection
# ---------------------------------------------------------------------------


def test_tampered_aad_ciphertext_and_cross_node_spoofing_rejected(harness: GatewayHarness) -> None:
    with TestClient(harness.app) as client:
        admin_token = _login(client, "admin@sentra.local", "AdminPassword!1")
        node_a, key_a = _register_node(client, admin_token, name="Node-A")
        node_b, key_b = _register_node(client, admin_token, name="Node-B")

        _, valid_frame, _, _ = _make_intrusion_frame(node_id=node_a, node_key=key_a, seq_counter=1)

        # Case A: Flip 1 byte inside 42-byte AAD (seq_counter field at offset 30)
        tampered_aad = bytearray(valid_frame)
        tampered_aad[30] ^= 0x01
        with client.websocket_connect(f"/ws/edge/{node_a}") as edge_ws:
            edge_ws.send_bytes(bytes(tampered_aad))
            with pytest.raises(WebSocketDisconnect) as exc_info:
                edge_ws.receive_bytes()
            assert exc_info.value.code == 1008

        # Case B: Flip 1 byte inside AES-GCM ciphertext
        tampered_ct = bytearray(valid_frame)
        tampered_ct[-5] ^= 0xFF
        with client.websocket_connect(f"/ws/edge/{node_a}") as edge_ws:
            edge_ws.send_bytes(bytes(tampered_ct))
            with pytest.raises(WebSocketDisconnect) as exc_info:
                edge_ws.receive_bytes()
            assert exc_info.value.code == 1008

        # Case C: Validly signed frame for Node B sent on Node A's WebSocket
        _, node_b_frame, _, _ = _make_intrusion_frame(node_id=node_b, node_key=key_b, seq_counter=1)
        with client.websocket_connect(f"/ws/edge/{node_a}") as edge_ws:
            edge_ws.send_bytes(node_b_frame)
            with pytest.raises(WebSocketDisconnect) as exc_info:
                edge_ws.receive_bytes()
            assert exc_info.value.code == 1008

        assert len(harness.events_repo.events) == 0
        assert harness.object_store.put_count == 0
        violations = [log for log in harness.audit_repo.logs if log.action == "EDGE_SECURITY_VIOLATION"]
        assert len(violations) == 3


# ---------------------------------------------------------------------------
# 4. Live FENCE_SYNC Push, Edge FENCE_ACK & Bidirectional HEARTBEAT
# ---------------------------------------------------------------------------


def test_live_fence_sync_push_fence_ack_and_heartbeat(harness: GatewayHarness) -> None:
    with TestClient(harness.app) as client:
        admin_token = _login(client, "admin@sentra.local", "AdminPassword!1")
        op_token = _login(client, "operator@sentra.local", "OperatorPassword!1")
        node_id, node_key = _register_node(client, admin_token)

        polygon = [[0.1, 0.2], [0.8, 0.2], [0.8, 0.9], [0.1, 0.9]]

        # Reject self-intersecting bowtie polygon with 422 via Phase 1 VirtualFencePolygon
        bad_resp = client.put(
            f"/api/v1/nodes/{node_id}/fence",
            json={"name": "Bowtie", "vertices": [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]},
            headers=_auth_header(op_token),
        )
        assert bad_resp.status_code == 422

        with (
            client.websocket_connect(
                "/ws/console", subprotocols=["sentra.v1", op_token]
            ) as console_ws,
            client.websocket_connect(f"/ws/edge/{node_id}") as edge_ws,
        ):
            # Operator updates virtual fence -> Core persists v1, writes audit, pushes FENCE_SYNC
            put_resp = client.put(
                f"/api/v1/nodes/{node_id}/fence",
                json={"name": "South Gate", "vertices": polygon, "is_active": True},
                headers=_auth_header(op_token),
            )
            assert put_resp.status_code == 200, put_resp.text
            put_body = put_resp.json()
            assert put_body["pushed_live"] is True
            assert put_body["fence"]["version"] == 1
            fence_id = UUID(put_body["fence"]["fence_id"])

            # Open edge socket receives signed FENCE_SYNC frame immediately
            sync_raw = edge_ws.receive_bytes()
            sync_frame = open_frame(sync_raw, lambda _n, _k: node_key)
            assert sync_frame.header.msg_type is MessageType.FENCE_SYNC
            assert isinstance(sync_frame.payload, FenceSyncPayload)
            assert sync_frame.payload.fence_id == fence_id
            assert sync_frame.payload.version == 1
            assert sync_frame.payload.name == "South Gate"
            assert len(sync_frame.payload.vertices) == 4

            # Edge replies with signed FENCE_ACK -> console receives FENCE_SYNC_ACK
            ack_frame = seal_control_frame(
                msg_type=MessageType.FENCE_ACK,
                node_id=node_id,
                key_id=1,
                session_epoch=100,
                seq_counter=1,
                key=node_key,
                payload=FenceAckPayload(fence_id=fence_id, version=1, applied=True, error=None),
            )
            edge_ws.send_bytes(ack_frame)
            ack_broadcast = console_ws.receive_json()
            assert ack_broadcast["type"] == "FENCE_SYNC_ACK"
            assert ack_broadcast["data"]["applied"] is True
            assert ack_broadcast["data"]["version"] == 1

            # Edge sends HEARTBEAT -> receives signed pong + console receives NODE_HEARTBEAT
            hb_frame = seal_control_frame(
                msg_type=MessageType.HEARTBEAT,
                node_id=node_id,
                key_id=1,
                session_epoch=100,
                seq_counter=2,
                key=node_key,
                payload=HeartbeatPayload(
                    uptime_s=420,
                    outbox_depth=0,
                    outbox_bytes=0,
                    active_fence_version=1,
                    cpu_temp_c=51.5,
                ),
            )
            edge_ws.send_bytes(hb_frame)
            pong = open_frame(edge_ws.receive_bytes(), lambda _n, _k: node_key)
            assert pong.header.msg_type is MessageType.HEARTBEAT
            hb_broadcast = console_ws.receive_json()
            assert hb_broadcast["type"] == "NODE_HEARTBEAT"
            assert hb_broadcast["data"]["uptime_s"] == 420
            assert hb_broadcast["data"]["cpu_temp_c"] == 51.5

        fence_audits = [log for log in harness.audit_repo.logs if log.action == "FENCE_UPDATED"]
        assert len(fence_audits) == 1
        assert fence_audits[0].details["version"] == 1


# ---------------------------------------------------------------------------
# 5. Dual-Token Authentication, Refresh Reuse Detection & Strict RBAC
# ---------------------------------------------------------------------------


def test_dual_token_auth_rotation_reuse_detection_and_rbac(harness: GatewayHarness) -> None:
    with TestClient(harness.app) as client:
        # Login sets HttpOnly refresh cookie + short-lived access token
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "operator@sentra.local", "password": "OperatorPassword!1"},
        )
        assert login_resp.status_code == 200
        login_body = login_resp.json()
        assert login_body["expires_in_seconds"] == 900
        assert "httponly" in login_resp.headers["set-cookie"].lower()
        cookie_v1 = client.cookies.get(REFRESH_COOKIE_NAME)
        assert cookie_v1 is not None

        op_token = login_body["access_token"]
        me_resp = client.get("/api/v1/auth/me", headers=_auth_header(op_token))
        assert me_resp.status_code == 200
        assert me_resp.json()["role"] == "OPERATOR"

        # Silent refresh rotates cookie_v1 -> cookie_v2
        refresh_resp = client.post("/api/v1/auth/refresh")
        assert refresh_resp.status_code == 200
        cookie_v2 = client.cookies.get(REFRESH_COOKIE_NAME)
        assert cookie_v2 is not None and cookie_v2 != cookie_v1

        # Replay of old rotated cookie_v1 must fail (401) AND revoke entire token family
        client.cookies.clear()
        client.cookies.set(REFRESH_COOKIE_NAME, cookie_v1)
        replay_resp = client.post("/api/v1/auth/refresh")
        assert replay_resp.status_code == 401

        # Because family was revoked on reuse detection, cookie_v2 must now ALSO fail (401)
        client.cookies.clear()
        client.cookies.set(REFRESH_COOKIE_NAME, cookie_v2)
        after_reuse = client.post("/api/v1/auth/refresh")
        assert after_reuse.status_code == 401

        # Re-login operator & test ADMIN session revocation
        client.cookies.clear()
        op_token = _login(client, "operator@sentra.local", "OperatorPassword!1")
        op_cookie = client.cookies.get(REFRESH_COOKIE_NAME)
        assert op_cookie is not None

        admin_token = _login(client, "admin@sentra.local", "AdminPassword!1")
        auditor_token = _login(client, "auditor@sentra.local", "AuditorPassword!1")

        # Seed a node and one event for RBAC testing
        node_id, node_key = _register_node(client, admin_token)
        with client.websocket_connect(f"/ws/edge/{node_id}") as edge_ws:
            event_id, frame, _, _ = _make_intrusion_frame(
                node_id=node_id, node_key=node_key, seq_counter=1
            )
            edge_ws.send_bytes(frame)
            edge_ws.receive_bytes()

        # AUDITOR: read-only access allowed; all mutations must return 403 Forbidden
        assert client.get("/api/v1/nodes", headers=_auth_header(auditor_token)).status_code == 200
        assert client.get("/api/v1/events", headers=_auth_header(auditor_token)).status_code == 200
        detail_resp = client.get(f"/api/v1/events/{event_id}", headers=_auth_header(auditor_token))
        assert detail_resp.status_code == 200
        assert "wide_presigned_url" in detail_resp.json()
        assert client.get("/api/v1/audit-logs", headers=_auth_header(auditor_token)).status_code == 200

        assert (
            client.patch(
                f"/api/v1/events/{event_id}/triage",
                json={"triage_status": "ACKNOWLEDGED"},
                headers=_auth_header(auditor_token),
            ).status_code
            == 403
        )
        assert (
            client.put(
                f"/api/v1/nodes/{node_id}/fence",
                json={"name": "Denied", "vertices": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]},
                headers=_auth_header(auditor_token),
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/nodes",
                json={"name": "Denied"},
                headers=_auth_header(auditor_token),
            ).status_code
            == 403
        )

        # OPERATOR: triage & fence updates allowed; node registration & audit logs forbidden (403)
        triage_resp = client.patch(
            f"/api/v1/events/{event_id}/triage",
            json={"triage_status": "ESCALATED", "note": "Guard dispatched"},
            headers=_auth_header(op_token),
        )
        assert triage_resp.status_code == 200
        assert triage_resp.json()["triage_status"] == "ESCALATED"

        assert (
            client.post(
                "/api/v1/nodes",
                json={"name": "Denied"},
                headers=_auth_header(op_token),
            ).status_code
            == 403
        )
        assert client.get("/api/v1/audit-logs", headers=_auth_header(op_token)).status_code == 403

        # ADMIN: revoke operator sessions -> operator's refresh cookie rejected
        revoke_resp = client.post(
            f"/api/v1/auth/revoke/{harness.operator.user_id}",
            headers=_auth_header(admin_token),
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["revoked_tokens"] >= 1
        client.cookies.clear()
        client.cookies.set(REFRESH_COOKIE_NAME, op_cookie)
        assert client.post("/api/v1/auth/refresh").status_code == 401

        # Unauthenticated / invalid token on /ws/console rejected with 1008
        with pytest.raises(WebSocketDisconnect) as ws_exc:
            with client.websocket_connect("/ws/console?token=invalid.jwt.token"):
                pass
        assert ws_exc.value.code == 1008

        # Audit logs recorded login, node registration, triage update, and admin revocation
        actions = {log.action for log in harness.audit_repo.logs}
        assert {"USER_LOGIN", "NODE_REGISTERED", "TRIAGE_UPDATED", "ADMIN_SESSION_REVOKED"} <= actions


# ---------------------------------------------------------------------------
# 6. Automated Retention Purge (MinIO-First Deletion + Partial-Failure Safety)
# ---------------------------------------------------------------------------


def test_retention_worker_deletes_minio_before_postgres_and_audits(harness: GatewayHarness) -> None:
    async def _run() -> None:
        node = await harness.nodes_repo.register_node(
            name="Retention-Node", location="Yard", actor_user_id=harness.admin.user_id
        )
        now = datetime.now(timezone.utc)

        async def _seed_event(seq: int, expires_delta: timedelta) -> IntrusionEventRow:
            eid = uuid4()
            detected_at = now - timedelta(days=31)
            wide_key, roi_key = build_evidence_keys(
                node_id=node.node_id, detected_at=detected_at, event_id=eid, image_format="jpeg"
            )
            wide_data = f"wide-{seq}".encode()
            roi_data = f"roi-{seq}".encode()
            await harness.object_store.put_evidence(object_key=wide_key, data=wide_data)
            await harness.object_store.put_evidence(object_key=roi_key, data=roi_data)
            row, _ = await harness.events_repo.insert_event_idempotent(
                event_id=eid,
                node_id=node.node_id,
                session_epoch=1,
                seq_counter=seq,
                fence_id=None,
                fence_version=1,
                detected_at=detected_at,
                confidence=0.88,
                bbox=(0.1, 0.1, 0.2, 0.4),
                ground_point=(0.2, 0.5),
                persistence_frames=3,
                wide_object_key=wide_key,
                wide_sha256=hashlib.sha256(wide_data).hexdigest(),
                roi_object_key=roi_key,
                roi_sha256=hashlib.sha256(roi_data).hexdigest(),
                expires_at=now + expires_delta,
            )
            return row

        exp_1 = await _seed_event(1, timedelta(hours=-2))
        exp_2 = await _seed_event(2, timedelta(minutes=-5))
        exp_partial = await _seed_event(3, timedelta(minutes=-1))
        fresh = await _seed_event(4, timedelta(days=15))

        # Simulate MinIO deletion failure for exp_partial's roi object -> its DB row must NOT be purged
        harness.object_store.fail_delete_keys.add(exp_partial.roi_object_key)
        harness.timeline.clear()

        purged = await harness.retention_worker.run_sweep_once(now=now)
        assert purged == 2

        # MinIO delete_objects MUST occur strictly before PostgreSQL row deletion
        assert harness.timeline == ["s3:delete:6", "db:delete:2"]

        assert exp_1.event_id not in harness.events_repo.events
        assert exp_2.event_id not in harness.events_repo.events
        assert exp_1.wide_object_key not in harness.object_store.objects
        assert exp_2.roi_object_key not in harness.object_store.objects

        # Partial-failure event stays in DB for next sweep; fresh event untouched
        assert exp_partial.event_id in harness.events_repo.events
        assert fresh.event_id in harness.events_repo.events
        assert fresh.wide_object_key in harness.object_store.objects
        assert fresh.roi_object_key in harness.object_store.objects

        purge_audits = [log for log in harness.audit_repo.logs if log.action == "RETENTION_PURGE"]
        assert len(purge_audits) == 1
        assert purge_audits[0].details["purged_event_count"] == 2
        assert purge_audits[0].details["purged_object_count"] == 4

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. Config Loader & HKDF Per-Node Key Isolation
# ---------------------------------------------------------------------------


def test_config_toml_env_override_and_hkdf_isolation(tmp_path: Path) -> None:
    cfg_file = tmp_path / "core.toml"
    cfg_file.write_text(
        "\n".join(
            [
                'postgres_dsn = "postgresql://u:p@db:5432/sentra"',
                'minio_endpoint = "minio:9000"',
                'minio_access_key = "ak"',
                'minio_secret_key = "sk"',
                f'jwt_secret_hex = "{"11" * 32}"',
                f'node_master_key_hex = "{"22" * 32}"',
                "evidence_retention_days = 30",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_core_config(
        config_path=cfg_file,
        environ={
            "SENTRA_CORE_EVIDENCE_RETENTION_DAYS": "45",
            "SENTRA_CORE_CORS_ORIGINS": "https://ops.sentra.local, https://admin.sentra.local",
        },
    )
    assert loaded.evidence_retention_days == 45
    assert loaded.cors_origins == ["https://ops.sentra.local", "https://admin.sentra.local"]

    node_a = uuid4()
    node_b = uuid4()
    key_a1 = derive_node_key(loaded.node_master_key, node_a, 1)
    key_a2 = derive_node_key(loaded.node_master_key, node_a, 2)
    key_b1 = derive_node_key(loaded.node_master_key, node_b, 1)
    assert len(key_a1) == 32
    assert len({key_a1, key_a2, key_b1}) == 3
