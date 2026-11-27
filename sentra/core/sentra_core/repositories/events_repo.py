"""Intrusion events repository: idempotent ingestion, triage + audit, and retention purge."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg
from sentra_protocol.models import NormalizedBBox, NormalizedPoint, TriageStatus

from .audit_repo import AuditRepository
from .records import ExpiredEventRef, IntrusionEventRow

_EVENT_COLUMNS: str = (
    "event_id, node_id, seq_counter, fence_id, fence_version, detected_at, received_at, "
    "confidence, bbox, ground_point, persistence_frames, wide_object_key, wide_sha256, "
    "roi_object_key, roi_sha256, triage_status, expires_at"
)


class EventsRepository(Protocol):
    """Idempotent intrusion event storage, querying, triage, and expiry sweep contract."""

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
    ) -> tuple[IntrusionEventRow, bool]: ...

    async def get_event(self, event_id: UUID) -> IntrusionEventRow | None: ...

    async def list_events(
        self,
        *,
        node_id: UUID | None = None,
        triage_status: TriageStatus | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IntrusionEventRow]: ...

    async def update_triage_status(
        self,
        *,
        event_id: UUID,
        new_status: TriageStatus,
        actor_user_id: UUID,
        note: str | None = None,
    ) -> IntrusionEventRow | None: ...

    async def fetch_expired_events(self, *, now: datetime, limit: int = 100) -> list[ExpiredEventRef]: ...

    async def delete_events_by_ids(self, event_ids: Sequence[UUID]) -> int: ...


class AsyncpgEventsRepository:
    """PostgreSQL 16 asyncpg implementation with atomic sequence + event + audit writes."""

    def __init__(self, pool: asyncpg.Pool, audit_repo: AuditRepository) -> None:
        self._pool = pool
        self._audit = audit_repo

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
        """Insert event idempotently and advance node watermark in one DB transaction.

        Returns (row, created) where created=False means event_id already existed.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                inserted = await conn.fetchrow(
                    f"""
                    INSERT INTO intrusion_events (
                        event_id, node_id, seq_counter, fence_id, fence_version,
                        detected_at, confidence, bbox, ground_point, persistence_frames,
                        wide_object_key, wide_sha256, roi_object_key, roi_sha256, expires_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb,
                        $10, $11, $12, $13, $14, $15
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING {_EVENT_COLUMNS}
                    """,
                    event_id,
                    node_id,
                    seq_counter,
                    fence_id,
                    fence_version,
                    detected_at,
                    confidence,
                    json.dumps(list(bbox)),
                    json.dumps(list(ground_point)),
                    persistence_frames,
                    wide_object_key,
                    wide_sha256,
                    roi_object_key,
                    roi_sha256,
                    expires_at,
                )
                if inserted is not None:
                    await conn.execute(
                        """
                        UPDATE edge_nodes
                        SET last_session_epoch = GREATEST(last_session_epoch, $2),
                            last_seq_counter = CASE
                                WHEN $2 > last_session_epoch THEN $3
                                ELSE GREATEST(last_seq_counter, $3)
                            END,
                            status = 'ONLINE',
                            last_heartbeat_at = NOW(),
                            updated_at = NOW()
                        WHERE node_id = $1
                        """,
                        node_id,
                        session_epoch,
                        seq_counter,
                    )
                    return _row_to_event(inserted), True

                existing = await conn.fetchrow(
                    f"SELECT {_EVENT_COLUMNS} FROM intrusion_events WHERE event_id = $1",
                    event_id,
                )
                assert existing is not None
                return _row_to_event(existing), False

    async def get_event(self, event_id: UUID) -> IntrusionEventRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_EVENT_COLUMNS} FROM intrusion_events WHERE event_id = $1",
                event_id,
            )
        return _row_to_event(row) if row is not None else None

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
        clauses: list[str] = []
        args: list[object] = []

        if node_id is not None:
            args.append(node_id)
            clauses.append(f"node_id = ${len(args)}")
        if triage_status is not None:
            args.append(triage_status)
            clauses.append(f"triage_status = ${len(args)}")
        if since is not None:
            args.append(since)
            clauses.append(f"detected_at >= ${len(args)}")
        if until is not None:
            args.append(until)
            clauses.append(f"detected_at <= ${len(args)}")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.extend([limit, offset])

        sql = f"""
            SELECT {_EVENT_COLUMNS}
            FROM intrusion_events
            {where_sql}
            ORDER BY received_at DESC
            LIMIT ${len(args) - 1} OFFSET ${len(args)}
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [_row_to_event(r) for r in rows]

    async def update_triage_status(
        self,
        *,
        event_id: UUID,
        new_status: TriageStatus,
        actor_user_id: UUID,
        note: str | None = None,
    ) -> IntrusionEventRow | None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"""
                    UPDATE intrusion_events
                    SET triage_status = $2
                    WHERE event_id = $1
                    RETURNING {_EVENT_COLUMNS}
                    """,
                    event_id,
                    new_status,
                )
                if row is None:
                    return None
                await self._audit.append_log(
                    actor_user_id=actor_user_id,
                    action="TRIAGE_UPDATED",
                    target_type="intrusion_event",
                    target_id=str(event_id),
                    details={"triage_status": new_status, "note": note},
                    conn=conn,
                )
        return _row_to_event(row)

    async def fetch_expired_events(self, *, now: datetime, limit: int = 100) -> list[ExpiredEventRef]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT event_id, wide_object_key, roi_object_key
                FROM intrusion_events
                WHERE expires_at <= $1
                ORDER BY expires_at ASC
                LIMIT $2
                """,
                now,
                limit,
            )
        return [
            ExpiredEventRef(
                event_id=r["event_id"],
                wide_object_key=str(r["wide_object_key"]),
                roi_object_key=str(r["roi_object_key"]),
            )
            for r in rows
        ]

    async def delete_events_by_ids(self, event_ids: Sequence[UUID]) -> int:
        if not event_ids:
            return 0
        async with self._pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM intrusion_events WHERE event_id = ANY($1::uuid[])",
                list(event_ids),
            )
        return int(res.split()[-1])


def _row_to_event(row: asyncpg.Record) -> IntrusionEventRow:
    raw_bbox = json.loads(row["bbox"]) if isinstance(row["bbox"], str) else row["bbox"]
    raw_gp = json.loads(row["ground_point"]) if isinstance(row["ground_point"], str) else row["ground_point"]
    return IntrusionEventRow(
        event_id=row["event_id"],
        node_id=row["node_id"],
        seq_counter=int(row["seq_counter"]),
        fence_id=row["fence_id"],
        fence_version=int(row["fence_version"]),
        detected_at=row["detected_at"],
        received_at=row["received_at"],
        confidence=float(row["confidence"]),
        bbox=(float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3])),
        ground_point=(float(raw_gp[0]), float(raw_gp[1])),
        persistence_frames=int(row["persistence_frames"]),
        wide_object_key=str(row["wide_object_key"]),
        wide_sha256=str(row["wide_sha256"]),
        roi_object_key=str(row["roi_object_key"]),
        roi_sha256=str(row["roi_sha256"]),
        triage_status=row["triage_status"],
        expires_at=row["expires_at"],
    )
