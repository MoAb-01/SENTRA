"""Asyncpg PostgreSQL 16 pool lifecycle and idempotent SQL migration runner."""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

DEFAULT_MIGRATIONS_DIR: Path = Path(__file__).resolve().parents[1] / "db" / "migrations"


class DatabasePool:
    """Manages asyncpg connection pool and idempotent startup migrations."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 2,
        max_size: int = 20,
        migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._migrations_dir = migrations_dir
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DatabasePool has not been initialized; call connect() first")
        return self._pool

    async def connect(self) -> None:
        """Create asyncpg connection pool."""
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
        )
        logger.info("Connected PostgreSQL asyncpg pool (min=%d max=%d)", self._min_size, self._max_size)

    async def run_migrations(self) -> list[str]:
        """Apply ordered .sql migrations idempotently using schema_migrations ledger."""
        applied: list[str] = []
        pool = self.pool

        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    TEXT        PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            existing = {
                row["version"]
                for row in await conn.fetch("SELECT version FROM schema_migrations")
            }

            migration_files = sorted(self._migrations_dir.glob("*.sql"))
            for sql_file in migration_files:
                version = sql_file.name
                if version in existing:
                    continue

                # If database was pre-bootstrapped outside the runner, detect existing users table
                if version == "001_initial_schema.sql":
                    users_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name = 'users'
                        )
                        """
                    )
                    if users_exists:
                        await conn.execute(
                            "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
                            version,
                        )
                        continue

                sql_body = sql_file.read_text(encoding="utf-8")
                await conn.execute(sql_body)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
                    version,
                )
                applied.append(version)
                logger.info("Applied PostgreSQL migration: %s", version)

        return applied

    async def healthcheck(self) -> bool:
        """Execute lightweight SELECT 1 probe against PostgreSQL."""
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            return val == 1

    async def close(self) -> None:
        """Gracefully close all pooled PostgreSQL connections."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Closed PostgreSQL asyncpg pool")
