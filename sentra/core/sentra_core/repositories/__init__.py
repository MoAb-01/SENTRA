"""PostgreSQL 16 repository contracts and asyncpg implementations."""

from .audit_repo import AsyncpgAuditRepository, AuditLogRecord, AuditRepository
from .auth_repo import AsyncpgAuthRepository, AuthRepository, RefreshTokenRecord, UserRecord
from .events_repo import AsyncpgEventsRepository, EventsRepository, ExpiredEventRef, IntrusionEventRow
from .nodes_repo import (
    AsyncpgNodesRepository,
    EdgeNodeRecord,
    NodesRepository,
    ReplayAttackError,
    ReplayCheckResult,
    VirtualFenceRecord,
)

__all__ = [
    "AsyncpgAuditRepository",
    "AsyncpgAuthRepository",
    "AsyncpgEventsRepository",
    "AsyncpgNodesRepository",
    "AuditLogRecord",
    "AuditRepository",
    "AuthRepository",
    "EdgeNodeRecord",
    "EventsRepository",
    "ExpiredEventRef",
    "IntrusionEventRow",
    "NodesRepository",
    "RefreshTokenRecord",
    "ReplayAttackError",
    "ReplayCheckResult",
    "UserRecord",
    "VirtualFenceRecord",
]
