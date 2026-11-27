"""Append-only audit_logs repository (immutability enforced by PostgreSQL trigger)."""

from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from .records import AuditLogRecord


class AuditRepository(Protocol):
    """Append-only audit log writer and paginated reader contract."""

    async def append_log(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> AuditLogRecord: ...

    async def list_logs(self, *, limit: int = 50, offset: int = 0) -> list[AuditLogRecord]: ...


class AsyncpgAuditRepository:
    """PostgreSQL 16 asyncpg implementation of append-only audit_logs."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append_log(
        self,
        *,
        actor_user_id: UUID | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> AuditLogRecord:
        payload_json = json.dumps(details or {})
        sql = """
            INSERT INTO audit_logs (actor_user_id, action, target_type, target_id, details)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING log_id, actor_user_id, action, target_type, target_id, details, created_at
        """
        if conn is not None:
            row = await conn.fetchrow(sql, actor_user_id, action, target_type, target_id, payload_json)
        else:
            async with self._pool.acquire() as acquired:
                row = await acquired.fetchrow(
                    sql, actor_user_id, action, target_type, target_id, payload_json
                )
        return _row_to_audit(row)

    async def list_logs(self, *, limit: int = 50, offset: int = 0) -> list[AuditLogRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT log_id, actor_user_id, action, target_type, target_id, details, created_at
                FROM audit_logs
                ORDER BY log_id DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
        return [_row_to_audit(r) for r in rows]


def _row_to_audit(row: asyncpg.Record) -> AuditLogRecord:
    raw_details = row["details"]
    details = json.loads(raw_details) if isinstance(raw_details, str) else dict(raw_details or {})
    return AuditLogRecord(
        log_id=int(row["log_id"]),
        actor_user_id=row["actor_user_id"],
        action=str(row["action"]),
        target_type=row["target_type"],
        target_id=row["target_id"],
        details=details,
        created_at=row["created_at"],
    )
