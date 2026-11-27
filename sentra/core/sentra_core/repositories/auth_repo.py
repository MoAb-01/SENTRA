"""Users and Dual-Token refresh_tokens repository (rotation, sliding expiry, revocation)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID, uuid4

import asyncpg

from .records import RefreshTokenRecord, UserRecord


class AuthRepository(Protocol):
    """User lookup and Dual-Token refresh session lifecycle contract."""

    async def get_user_by_email(self, email: str) -> UserRecord | None: ...

    async def get_user_by_id(self, user_id: UUID) -> UserRecord | None: ...

    async def issue_refresh_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        inactivity_days: int,
        absolute_days: int,
        token_family_id: UUID | None = None,
    ) -> RefreshTokenRecord: ...

    async def rotate_refresh_token(
        self,
        *,
        old_token_hash: str,
        new_token_hash: str,
        inactivity_days: int,
    ) -> tuple[UserRecord, RefreshTokenRecord] | None: ...

    async def revoke_token_by_hash(self, token_hash: str, reason: str = "USER_LOGOUT") -> bool: ...

    async def revoke_all_user_tokens(self, user_id: UUID, reason: str = "ADMIN_REVOCATION") -> int: ...


class AsyncpgAuthRepository:
    """PostgreSQL 16 asyncpg implementation with refresh-token reuse detection."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, email, password_hash, role, is_active, created_at, updated_at
                FROM users WHERE email = $1
                """,
                email,
            )
        return _row_to_user(row) if row is not None else None

    async def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, email, password_hash, role, is_active, created_at, updated_at
                FROM users WHERE user_id = $1
                """,
                user_id,
            )
        return _row_to_user(row) if row is not None else None

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

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO refresh_tokens (
                    token_id, user_id, token_family_id, token_hash,
                    issued_at, last_used_at, sliding_expires_at, absolute_expires_at
                ) VALUES ($1, $2, $3, $4, $5, $5, $6, $7)
                """,
                token_id,
                user_id,
                family_id,
                token_hash,
                now,
                slide_exp,
                abs_exp,
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
        """Atomically rotate a refresh token; revoke entire family on replay reuse."""
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT token_id, user_id, token_family_id, sliding_expires_at,
                           absolute_expires_at, rotated_at, revoked_at
                    FROM refresh_tokens
                    WHERE token_hash = $1
                    FOR UPDATE
                    """,
                    old_token_hash,
                )
                if row is None:
                    return None

                # Refresh token reuse detected -> revoke entire token family immediately
                if row["rotated_at"] is not None or row["revoked_at"] is not None:
                    await conn.execute(
                        """
                        UPDATE refresh_tokens
                        SET revoked_at = COALESCE(revoked_at, $2),
                            revoked_reason = COALESCE(revoked_reason, 'TOKEN_REUSE_DETECTED')
                        WHERE token_family_id = $1
                        """,
                        row["token_family_id"],
                        now,
                    )
                    return None

                # Enforce sliding inactivity & absolute expiration limits
                if now >= row["sliding_expires_at"] or now >= row["absolute_expires_at"]:
                    await conn.execute(
                        "UPDATE refresh_tokens SET revoked_at = $2, revoked_reason = 'EXPIRED' WHERE token_id = $1",
                        row["token_id"],
                        now,
                    )
                    return None

                user_row = await conn.fetchrow(
                    """
                    SELECT user_id, email, password_hash, role, is_active, created_at, updated_at
                    FROM users WHERE user_id = $1
                    """,
                    row["user_id"],
                )
                if user_row is None or not bool(user_row["is_active"]):
                    return None

                await conn.execute(
                    "UPDATE refresh_tokens SET rotated_at = $2, last_used_at = $2 WHERE token_id = $1",
                    row["token_id"],
                    now,
                )

                new_id = uuid4()
                abs_exp: datetime = row["absolute_expires_at"]
                slide_exp = min(abs_exp, now + timedelta(days=inactivity_days))
                await conn.execute(
                    """
                    INSERT INTO refresh_tokens (
                        token_id, user_id, token_family_id, token_hash,
                        issued_at, last_used_at, sliding_expires_at, absolute_expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $5, $6, $7)
                    """,
                    new_id,
                    row["user_id"],
                    row["token_family_id"],
                    new_token_hash,
                    now,
                    slide_exp,
                    abs_exp,
                )

                return (
                    _row_to_user(user_row),
                    RefreshTokenRecord(
                        token_id=new_id,
                        user_id=row["user_id"],
                        token_family_id=row["token_family_id"],
                        sliding_expires_at=slide_exp,
                        absolute_expires_at=abs_exp,
                    ),
                )

    async def revoke_token_by_hash(self, token_hash: str, reason: str = "USER_LOGOUT") -> bool:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            res = await conn.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = $2, revoked_reason = $3
                WHERE token_hash = $1 AND revoked_at IS NULL
                """,
                token_hash,
                now,
                reason,
            )
        return not res.endswith("0")

    async def revoke_all_user_tokens(self, user_id: UUID, reason: str = "ADMIN_REVOCATION") -> int:
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            res = await conn.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = $2, revoked_reason = $3
                WHERE user_id = $1 AND revoked_at IS NULL
                """,
                user_id,
                now,
                reason,
            )
        return int(res.split()[-1])


def _row_to_user(row: asyncpg.Record) -> UserRecord:
    return UserRecord(
        user_id=row["user_id"],
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        role=row["role"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
