"""Async WebSocket uplink client: FIFO outbox drain, FENCE_SYNC, and heartbeats."""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

import websockets
from websockets.asyncio.client import ClientConnection
from sentra_protocol.constants import MAX_FRAME_SIZE, MessageType
from sentra_protocol.crypto import open_frame, seal_control_frame
from sentra_protocol.errors import InvalidKeyError, SentraProtocolError
from sentra_protocol.models import (
    EventAckPayload,
    FenceAckPayload,
    FenceSyncPayload,
    HeartbeatPayload,
)

from .geofence import AtomicFenceStore, FencePolygon
from .outbox import TransactionalOutbox

logger = logging.getLogger(__name__)

_MIN_RECONNECT_SEC: float = 0.5
_MAX_RECONNECT_SEC: float = 30.0
_DRAIN_POLL_IDLE_SEC: float = 0.25
_DRAIN_BATCH_SIZE: int = 8


class UplinkWorker:
    """Asyncio WebSocket uplink handling encrypted binary drain and Core control messages.

    Disables WebSocket permessage-deflate (compression=None) because AES-256-GCM
    ciphertext and JPEG/WebP images are high-entropy incompressible buffers.
    """

    def __init__(
        self,
        *,
        gateway_ws_url: str,
        node_id: UUID,
        key_id: int,
        encryption_key: bytes,
        outbox: TransactionalOutbox,
        fence_store: AtomicFenceStore,
        heartbeat_interval_sec: float = 15.0,
        drain_poll_sec: float = _DRAIN_POLL_IDLE_SEC,
        min_reconnect_sec: float = _MIN_RECONNECT_SEC,
        max_reconnect_sec: float = _MAX_RECONNECT_SEC,
    ) -> None:
        self._gateway_ws_url = gateway_ws_url
        self._node_id = node_id
        self._key_id = key_id
        self._encryption_key = encryption_key
        self._outbox = outbox
        self._fence_store = fence_store
        self._heartbeat_interval_sec = heartbeat_interval_sec
        self._drain_poll_sec = drain_poll_sec
        self._min_reconnect_sec = min_reconnect_sec
        self._max_reconnect_sec = max_reconnect_sec

        self._started_monotonic: float = time.monotonic()
        self._last_pong_monotonic: float = 0.0
        self._stop_event: asyncio.Event | None = None

    @property
    def last_pong_monotonic(self) -> float:
        return self._last_pong_monotonic

    def request_stop(self) -> None:
        """Signal the uplink coroutine to shut down cleanly."""
        if self._stop_event is not None:
            self._stop_event.set()

    def _resolve_key(self, node_id: UUID, key_id: int) -> bytes:
        if node_id != self._node_id or key_id != self._key_id:
            raise InvalidKeyError(f"Key mismatch for node={node_id} key_id={key_id}")
        return self._encryption_key

    async def run(self, stop_event: asyncio.Event | None = None) -> None:
        """Maintain authenticated WebSocket connection until stop_event is set."""
        self._stop_event = stop_event or asyncio.Event()
        backoff = self._min_reconnect_sec

        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    self._gateway_ws_url,
                    compression=None,  # Mandatory: never deflate AES-GCM ciphertext
                    ping_interval=None,
                    max_size=MAX_FRAME_SIZE,
                ) as ws:
                    logger.info("Connected to Core WebSocket gateway: %s", self._gateway_ws_url)
                    backoff = self._min_reconnect_sec
                    await self._run_session(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Core WebSocket disconnected (%s); reconnecting in %.2fs",
                    exc,
                    backoff,
                )
            finally:
                self._outbox.requeue_all_in_flight()

            if self._stop_event.is_set():
                break
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
            except TimeoutError:
                pass
            backoff = min(backoff * 2.0, self._max_reconnect_sec)

    async def _run_session(self, ws: ClientConnection) -> None:
        assert self._stop_event is not None
        send_lock = asyncio.Lock()

        tasks = [
            asyncio.create_task(self._drain_loop(ws, send_lock), name="sentra-drain"),
            asyncio.create_task(self._inbound_loop(ws, send_lock), name="sentra-inbound"),
            asyncio.create_task(self._heartbeat_loop(ws, send_lock), name="sentra-heartbeat"),
            asyncio.create_task(self._stop_event.wait(), name="sentra-stop-wait"),
        ]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            # Surface socket errors from the task that terminated first
            for task in done:
                if task.get_name() != "sentra-stop-wait":
                    task.result()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def _drain_loop(self, ws: ClientConnection, send_lock: asyncio.Lock) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            batch = self._outbox.claim_next_batch(limit=_DRAIN_BATCH_SIZE)
            if not batch:
                await asyncio.sleep(self._drain_poll_sec)
                continue

            for record in batch:
                try:
                    async with send_lock:
                        await ws.send(record.wire_frame)
                except Exception:
                    self._outbox.schedule_retry(record.event_id)
                    raise

    async def _inbound_loop(self, ws: ClientConnection, send_lock: asyncio.Lock) -> None:
        async for raw_message in ws:
            if not isinstance(raw_message, (bytes, bytearray)):
                logger.warning("Ignoring unexpected non-binary WebSocket message from Core")
                continue

            try:
                frame = open_frame(bytes(raw_message), self._resolve_key)
            except SentraProtocolError as exc:
                logger.error("Rejected invalid/unauthenticated Core control frame: %s", exc)
                continue

            payload = frame.payload
            if isinstance(payload, EventAckPayload):
                self._outbox.mark_acked(str(payload.event_id))
            elif isinstance(payload, HeartbeatPayload):
                self._last_pong_monotonic = time.monotonic()
            elif isinstance(payload, FenceSyncPayload):
                await self._handle_fence_sync(ws, send_lock, payload)

    async def _handle_fence_sync(
        self,
        ws: ClientConnection,
        send_lock: asyncio.Lock,
        sync: FenceSyncPayload,
    ) -> None:
        try:
            polygon = FencePolygon.from_sync_payload(sync)
            snapshot = self._fence_store.upsert_fence(polygon)
            self._outbox.save_fences(snapshot)
            ack = FenceAckPayload(
                fence_id=sync.fence_id,
                version=sync.version,
                applied=True,
                error=None,
            )
            logger.info(
                "Applied FENCE_SYNC fence_id=%s version=%d active=%s",
                sync.fence_id,
                sync.version,
                sync.is_active,
            )
        except Exception as exc:
            logger.exception("Failed applying FENCE_SYNC fence_id=%s", sync.fence_id)
            ack = FenceAckPayload(
                fence_id=sync.fence_id,
                version=sync.version,
                applied=False,
                error=str(exc)[:500],
            )

        epoch, seq = self._outbox.allocate_control_seq()
        ack_frame = seal_control_frame(
            msg_type=MessageType.FENCE_ACK,
            node_id=self._node_id,
            key_id=self._key_id,
            session_epoch=epoch,
            seq_counter=seq,
            key=self._encryption_key,
            payload=ack,
        )
        async with send_lock:
            await ws.send(ack_frame)

    async def _heartbeat_loop(self, ws: ClientConnection, send_lock: asyncio.Lock) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            stats = self._outbox.get_stats()
            hb = HeartbeatPayload(
                uptime_s=int(time.monotonic() - self._started_monotonic),
                outbox_depth=stats.pending_count + stats.in_flight_count,
                outbox_bytes=stats.total_bytes,
                active_fence_version=self._fence_store.active_version(),
                cpu_temp_c=None,
            )
            epoch, seq = self._outbox.allocate_control_seq()
            frame = seal_control_frame(
                msg_type=MessageType.HEARTBEAT,
                node_id=self._node_id,
                key_id=self._key_id,
                session_epoch=epoch,
                seq_counter=seq,
                key=self._encryption_key,
                payload=hb,
            )
            async with send_lock:
                await ws.send(frame)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._heartbeat_interval_sec
                )
            except TimeoutError:
                continue
