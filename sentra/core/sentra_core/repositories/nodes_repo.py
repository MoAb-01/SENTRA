"""Edge nodes & versioned virtual fences repository with row-locked replay protection."""

from __future__ import annotations

import json
import logging
from typing import Protocol
from uuid import UUID, uuid4

import asyncpg
from sentra_protocol.crypto import validate_replay_watermark
from sentra_protocol.errors import ReplayError
from sentra_protocol.models import NodeStatus, NormalizedPoint

from .audit_repo import AuditRepository
from .records import EdgeNodeRecord, ReplayCheckResult, VirtualFenceRecord

logger = logging.getLogger(__name__)


class ReplayAttackError(ReplayError):
    """Raised when an incoming edge packet violates monotonic epoch/sequence watermarks."""


class NodesRepository(Protocol):
    """Edge node registration, replay-watermark verification, and fence versioning contract."""

    async def get_node(self, node_id: UUID) -> EdgeNodeRecord | None: ...

    async def list_nodes(self) -> list[EdgeNodeRecord]: ...

    async def register_node(
        self, *, name: str, location: str, actor_user_id: UUID
    ) -> EdgeNodeRecord: ...

    async def check_replay_for_event(
        self, *, node_id: UUID, session_epoch: int, seq_counter: int, event_id: UUID
    ) -> ReplayCheckResult: ...

    async def update_heartbeat(self, *, node_id: UUID, status: NodeStatus = "ONLINE") -> None: ...

    async def get_active_fence(self, node_id: UUID) -> VirtualFenceRecord | None: ...

    async def upsert_fence_version(
        self,
        *,
        node_id: UUID,
        name: str,
        vertices: list[NormalizedPoint],
        is_active: bool,
        actor_user_id: UUID,
    ) -> VirtualFenceRecord: ...


class AsyncpgNodesRepository:
    """PostgreSQL 16 asyncpg implementation with SELECT ... FOR UPDATE replay defense."""

    def __init__(self, pool: asyncpg.Pool, audit_repo: AuditRepository) -> None:
        self._pool = pool
        self._audit = audit_repo

    async def get_node(self, node_id: UUID) -> EdgeNodeRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT node_id, name, location, active_key_id, last_seq_counter,
                       last_session_epoch, status, last_heartbeat_at, created_at, updated_at
                FROM edge_nodes WHERE node_id = $1
                """,
                node_id,
            )
        return _row_to_node(row) if row is not None else None

    async def list_nodes(self) -> list[EdgeNodeRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT node_id, name, location, active_key_id, last_seq_counter,
                       last_session_epoch, status, last_heartbeat_at, created_at, updated_at
                FROM edge_nodes ORDER BY created_at DESC
                """
            )
        return [_row_to_node(r) for r in rows]

    async def register_node(
        self, *, name: str, location: str, actor_user_id: UUID
    ) -> EdgeNodeRecord:
        node_id = uuid4()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO edge_nodes (node_id, name, location, active_key_id, status)
                    VALUES ($1, $2, $3, 1, 'OFFLINE')
                    RETURNING node_id, name, location, active_key_id, last_seq_counter,
                              last_session_epoch, status, last_heartbeat_at, created_at, updated_at
                    """,
                    node_id,
                    name,
                    location,
                )
                await self._audit.append_log(
                    actor_user_id=actor_user_id,
                    action="NODE_REGISTERED",
                    target_type="edge_node",
                    target_id=str(node_id),
                    details={"name": name, "location": location, "active_key_id": 1},
                    conn=conn,
                )
        return _row_to_node(row)

    async def check_replay_for_event(
        self, *, node_id: UUID, session_epoch: int, seq_counter: int, event_id: UUID
    ) -> ReplayCheckResult:
        """Row-locked replay watermark validation prior to object storage upload."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                node_row = await conn.fetchrow(
                    """
                    SELECT last_seq_counter, last_session_epoch, status
                    FROM edge_nodes
                    WHERE node_id = $1
                    FOR UPDATE
                    """,
                    node_id,
                )
                if node_row is None or node_row["status"] == "REVOKED":
                    raise ReplayAttackError(f"Node {node_id} is unregistered or revoked")

                known_dup = bool(
                    await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM intrusion_events WHERE event_id = $1 AND node_id = $2)",
                        event_id,
                        node_id,
                    )
                )
                try:
                    is_fresh = validate_replay_watermark(
                        incoming_epoch=session_epoch,
                        incoming_seq=seq_counter,
                        last_epoch=int(node_row["last_session_epoch"]),
                        last_seq=int(node_row["last_seq_counter"]),
                        is_known_duplicate_event=known_dup,
                    )
                except ReplayError as exc:
                    logger.warning(
                        "Replay attack rejected for node=%s epoch=%d seq=%d: %s",
                        node_id,
                        session_epoch,
                        seq_counter,
                        exc,
                    )
                    raise ReplayAttackError(str(exc)) from exc

                return ReplayCheckResult(
                    is_duplicate_event=not is_fresh,
                    accepted_epoch=session_epoch,
                    accepted_seq=seq_counter,
                )

    async def update_heartbeat(self, *, node_id: UUID, status: NodeStatus = "ONLINE") -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE edge_nodes
                SET status = $2, last_heartbeat_at = NOW(), updated_at = NOW()
                WHERE node_id = $1 AND status != 'REVOKED'
                """,
                node_id,
                status,
            )

    async def get_active_fence(self, node_id: UUID) -> VirtualFenceRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT fence_id, node_id, name, version, vertices, is_active, created_by, created_at
                FROM virtual_fences
                WHERE node_id = $1 AND is_active = TRUE
                ORDER BY version DESC
                LIMIT 1
                """,
                node_id,
            )
        return _row_to_fence(row) if row is not None else None

    async def upsert_fence_version(
        self,
        *,
        node_id: UUID,
        name: str,
        vertices: list[NormalizedPoint],
        is_active: bool,
        actor_user_id: UUID,
    ) -> VirtualFenceRecord:
        fence_id = uuid4()
        verts_json = json.dumps([[float(x), float(y)] for x, y in vertices])
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                max_ver = await conn.fetchval(
                    "SELECT COALESCE(MAX(version), 0) FROM virtual_fences WHERE node_id = $1",
                    node_id,
                )
                next_version = int(max_ver) + 1
                await conn.execute(
                    "UPDATE virtual_fences SET is_active = FALSE WHERE node_id = $1 AND is_active = TRUE",
                    node_id,
                )
                row = await conn.fetchrow(
                    """
                    INSERT INTO virtual_fences (fence_id, node_id, name, version, vertices, is_active, created_by)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                    RETURNING fence_id, node_id, name, version, vertices, is_active, created_by, created_at
                    """,
                    fence_id,
                    node_id,
                    name,
                    next_version,
                    verts_json,
                    is_active,
                    actor_user_id,
                )
                await self._audit.append_log(
                    actor_user_id=actor_user_id,
                    action="FENCE_UPDATED",
                    target_type="virtual_fence",
                    target_id=str(fence_id),
                    details={"node_id": str(node_id), "version": next_version, "vertex_count": len(vertices)},
                    conn=conn,
                )
        return _row_to_fence(row)


def _row_to_node(row: asyncpg.Record) -> EdgeNodeRecord:
    return EdgeNodeRecord(
        node_id=row["node_id"],
        name=str(row["name"]),
        location=str(row["location"]),
        active_key_id=int(row["active_key_id"]),
        last_seq_counter=int(row["last_seq_counter"]),
        last_session_epoch=int(row["last_session_epoch"]),
        status=row["status"],
        last_heartbeat_at=row["last_heartbeat_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_fence(row: asyncpg.Record) -> VirtualFenceRecord:
    raw = row["vertices"]
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    vertices: list[NormalizedPoint] = [(float(pt[0]), float(pt[1])) for pt in parsed]
    return VirtualFenceRecord(
        fence_id=row["fence_id"],
        node_id=row["node_id"],
        name=str(row["name"]),
        version=int(row["version"]),
        vertices=vertices,
        is_active=bool(row["is_active"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )
