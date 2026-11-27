"""Background asyncio retention purge worker (MinIO objects first, then PostgreSQL + audit)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from .object_store import ObjectStore
from .repositories.audit_repo import AuditRepository
from .repositories.events_repo import EventsRepository

logger = logging.getLogger(__name__)


class RetentionWorker:
    """Periodically purges expired evidence objects from MinIO before removing DB rows."""

    def __init__(
        self,
        *,
        events_repo: EventsRepository,
        audit_repo: AuditRepository,
        object_store: ObjectStore,
        sweep_interval_sec: int = 3600,
        batch_size: int = 100,
    ) -> None:
        self._events_repo = events_repo
        self._audit_repo = audit_repo
        self._object_store = object_store
        self._sweep_interval_sec = sweep_interval_sec
        self._batch_size = batch_size

    async def run_sweep_once(self, *, now: datetime | None = None) -> int:
        """Delete expired MinIO objects first, then purge matching Postgres rows and write audit log."""
        sweep_time = datetime.now(timezone.utc) if now is None else now
        expired = await self._events_repo.fetch_expired_events(now=sweep_time, limit=self._batch_size)
        if not expired:
            return 0

        keys_to_delete: list[str] = []
        for item in expired:
            keys_to_delete.append(item.wide_object_key)
            keys_to_delete.append(item.roi_object_key)

        # Delete MinIO objects FIRST so orphaned encrypted blobs are never left behind
        deleted_keys = set(await self._object_store.delete_objects(keys_to_delete))

        # Only delete DB rows whose wide and roi objects were confirmed purged from MinIO
        purgeable_ids: list[UUID] = [
            item.event_id
            for item in expired
            if item.wide_object_key in deleted_keys and item.roi_object_key in deleted_keys
        ]
        if not purgeable_ids:
            return 0

        deleted_rows = await self._events_repo.delete_events_by_ids(purgeable_ids)
        await self._audit_repo.append_log(
            actor_user_id=None,
            action="RETENTION_PURGE",
            target_type="intrusion_event",
            target_id=None,
            details={
                "purged_event_count": deleted_rows,
                "purged_object_count": len(purgeable_ids) * 2,
                "sweep_time": sweep_time.isoformat(),
            },
        )
        logger.info(
            "Retention sweep purged %d expired intrusion event(s) and %d MinIO object(s)",
            deleted_rows,
            len(purgeable_ids) * 2,
        )
        return deleted_rows

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Run periodic retention sweeps until stop_event is signaled."""
        while not stop_event.is_set():
            try:
                await self.run_sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unhandled error during retention sweep")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=float(self._sweep_interval_sec))
            except TimeoutError:
                continue
