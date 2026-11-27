"""FastAPI application factory, lifespan startup/shutdown, and healthcheck endpoint."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth_router, console_ws_router, event_router, node_router
from .config import CoreConfig, load_core_config
from .db import DatabasePool
from .object_store import MinioObjectStore, ObjectStore
from .repositories import (
    AsyncpgAuditRepository,
    AsyncpgAuthRepository,
    AsyncpgEventsRepository,
    AsyncpgNodesRepository,
    AuditRepository,
    AuthRepository,
    EventsRepository,
    NodesRepository,
)
from .retention import RetentionWorker
from .ws import ConnectionRegistry, edge_ws_router

logger = logging.getLogger("sentra_core")


@dataclass(slots=True)
class CoreDependencies:
    """Explicit dependency container for production lifespan and clean test injection."""

    config: CoreConfig
    auth_repo: AuthRepository
    nodes_repo: NodesRepository
    events_repo: EventsRepository
    audit_repo: AuditRepository
    object_store: ObjectStore
    registry: ConnectionRegistry
    retention_worker: RetentionWorker
    db_pool: DatabasePool | None = None


def _attach_state(app: FastAPI, deps: CoreDependencies) -> None:
    app.state.config = deps.config
    app.state.auth_repo = deps.auth_repo
    app.state.nodes_repo = deps.nodes_repo
    app.state.events_repo = deps.events_repo
    app.state.audit_repo = deps.audit_repo
    app.state.object_store = deps.object_store
    app.state.registry = deps.registry
    app.state.retention_worker = deps.retention_worker
    app.state.db_pool = deps.db_pool


def create_app(
    config: CoreConfig | None = None,
    *,
    deps_override: CoreDependencies | None = None,
) -> FastAPI:
    """Build the SENTRA Core FastAPI application with managed Postgres, MinIO, and retention."""
    resolved_config = deps_override.config if deps_override is not None else (config or load_core_config())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if deps_override is not None:
            _attach_state(app, deps_override)
            yield
            return

        db_pool = DatabasePool(resolved_config.postgres_dsn)
        await db_pool.connect()
        await db_pool.run_migrations()

        object_store = MinioObjectStore(
            endpoint=resolved_config.minio_endpoint,
            access_key=resolved_config.minio_access_key,
            secret_key=resolved_config.minio_secret_key,
            bucket=resolved_config.minio_bucket,
            secure=resolved_config.minio_secure,
            presigned_ttl_sec=resolved_config.presigned_ttl_sec,
        )
        await object_store.ensure_bucket()

        audit_repo = AsyncpgAuditRepository(db_pool.pool)
        auth_repo = AsyncpgAuthRepository(db_pool.pool)
        nodes_repo = AsyncpgNodesRepository(db_pool.pool, audit_repo)
        events_repo = AsyncpgEventsRepository(db_pool.pool, audit_repo)
        registry = ConnectionRegistry()
        retention_worker = RetentionWorker(
            events_repo=events_repo,
            audit_repo=audit_repo,
            object_store=object_store,
            sweep_interval_sec=resolved_config.retention_sweep_interval_sec,
        )

        deps = CoreDependencies(
            config=resolved_config,
            auth_repo=auth_repo,
            nodes_repo=nodes_repo,
            events_repo=events_repo,
            audit_repo=audit_repo,
            object_store=object_store,
            registry=registry,
            retention_worker=retention_worker,
            db_pool=db_pool,
        )
        _attach_state(app, deps)

        stop_event = asyncio.Event()
        retention_task = asyncio.create_task(
            retention_worker.run_forever(stop_event),
            name="sentra-retention-worker",
        )
        try:
            yield
        finally:
            stop_event.set()
            retention_task.cancel()
            await asyncio.gather(retention_task, return_exceptions=True)
            await db_pool.close()

    app = FastAPI(
        title="SENTRA Central Cryptographic Gateway",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(node_router)
    app.include_router(event_router)
    app.include_router(edge_ws_router)
    app.include_router(console_ws_router)

    @app.get("/healthz", tags=["system"])
    async def healthcheck() -> dict[str, object]:
        db_ok = True
        pool: DatabasePool | None = getattr(app.state, "db_pool", None)
        if pool is not None:
            db_ok = await pool.healthcheck()
        return {"status": "ok" if db_ok else "degraded", "database": db_ok}

    return app


def run_cli() -> None:
    """Launch SENTRA Core via Uvicorn with WebSocket permessage-deflate disabled."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    uvicorn.run(
        "sentra_core.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        ws_per_message_deflate=False,
    )
