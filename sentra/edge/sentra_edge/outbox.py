"""Thread-safe SQLite WAL transactional outbox queue with FIFO ring-buffer eviction."""

from __future__ import annotations

import logging
import random
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sentra_protocol.crypto import seal_intrusion_event
from sentra_protocol.models import ImageFormat, NormalizedBBox, NormalizedPoint

from .geofence import FencePolygon
from .storage import DEFAULT_SCHEMA_PATH, EdgeStateStore

logger = logging.getLogger(__name__)

_BASE_BACKOFF_MS: int = 1_000
_MAX_BACKOFF_MS: int = 60_000


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    """Single claimed pre-encrypted wire frame ready for WebSocket transmission."""

    event_id: str
    seq_counter: int
    wire_frame: bytes
    frame_size_bytes: int
    attempt_count: int
    created_at: int


@dataclass(frozen=True, slots=True)
class OutboxStats:
    """Point-in-time outbox telemetry for HEARTBEAT frames."""

    pending_count: int
    in_flight_count: int
    total_bytes: int
    last_seq_counter: int
    session_epoch: int


class TransactionalOutbox:
    """Crash-safe SQLite WAL outbox with atomic sealing, backoff, and quota eviction."""

    def __init__(
        self,
        *,
        db_path: Path,
        node_id: UUID,
        key_id: int,
        encryption_key: bytes,
        max_outbox_bytes: int = 536_870_912,
        schema_path: Path = DEFAULT_SCHEMA_PATH,
    ) -> None:
        self._node_id = node_id
        self._key_id = key_id
        self._encryption_key = encryption_key
        self._max_outbox_bytes = max_outbox_bytes
        self._store = EdgeStateStore(
            db_path=db_path,
            node_id=node_id,
            key_id=key_id,
            schema_path=schema_path,
        )
        recovered = self.requeue_all_in_flight()
        if recovered > 0:
            logger.warning("Recovered %d stranded IN_FLIGHT outbox rows to PENDING", recovered)

    def allocate_control_seq(self) -> tuple[int, int]:
        """Allocate next monotonic (session_epoch, seq_counter) for control frames."""
        return self._store.allocate_control_seq()

    def save_fences(self, fences: Sequence[FencePolygon]) -> None:
        """Persist synced virtual fences for offline cold-start resilience."""
        self._store.save_fences(fences)

    def load_cached_fences(self) -> list[FencePolygon]:
        """Load persisted virtual fences from SQLite."""
        return self._store.load_cached_fences()

    def enqueue_intrusion(
        self,
        *,
        event_id: UUID,
        fence_id: UUID,
        fence_version: int,
        confidence: float,
        bbox: NormalizedBBox,
        ground_point: NormalizedPoint,
        persistence_frames: int,
        wide_bytes: bytes,
        roi_bytes: bytes,
        image_format: ImageFormat = "jpeg",
        timestamp_ns: int | None = None,
    ) -> OutboxRecord:
        """Atomically increment seq_counter, seal AES-256-GCM frame, enforce quota, and persist."""
        now_ms = int(time.time() * 1000)
        ts_ns = time.time_ns() if timestamp_ns is None else timestamp_ns

        with self._store.write_transaction() as conn:
            session_epoch, seq = self._store.next_sequence_in_tx(conn, now_ms)
            wire_frame = seal_intrusion_event(
                node_id=self._node_id,
                key_id=self._key_id,
                session_epoch=session_epoch,
                seq_counter=seq,
                key=self._encryption_key,
                event_id=event_id,
                fence_id=fence_id,
                fence_version=fence_version,
                confidence=confidence,
                bbox=bbox,
                ground_point=ground_point,
                persistence_frames=persistence_frames,
                wide_bytes=wide_bytes,
                roi_bytes=roi_bytes,
                image_format=image_format,
                timestamp_ns=ts_ns,
            )
            frame_size = len(wire_frame)
            if frame_size > self._max_outbox_bytes:
                raise ValueError(
                    f"Single sealed frame ({frame_size} B) exceeds max_outbox_bytes ({self._max_outbox_bytes} B)"
                )

            self._enforce_ring_buffer_quota(conn, incoming_bytes=frame_size)
            conn.execute(
                """
                INSERT INTO outbox_events (
                    event_id, seq_counter, state, wire_frame, frame_size_bytes,
                    attempt_count, next_retry_at, created_at
                ) VALUES (?, ?, 'PENDING', ?, ?, 0, ?, ?)
                """,
                (str(event_id), seq, wire_frame, frame_size, now_ms, now_ms),
            )
            return OutboxRecord(
                event_id=str(event_id),
                seq_counter=seq,
                wire_frame=wire_frame,
                frame_size_bytes=frame_size,
                attempt_count=0,
                created_at=now_ms,
            )

    def _enforce_ring_buffer_quota(self, conn: sqlite3.Connection, incoming_bytes: int) -> None:
        """Evict ACKED rows first, then oldest PENDING rows (FIFO) until quota permits insert."""
        total_bytes = int(
            conn.execute("SELECT COALESCE(SUM(frame_size_bytes), 0) FROM outbox_events").fetchone()[0]
        )
        if total_bytes + incoming_bytes <= self._max_outbox_bytes:
            return

        if conn.execute("DELETE FROM outbox_events WHERE state = 'ACKED'").rowcount > 0:
            total_bytes = int(
                conn.execute("SELECT COALESCE(SUM(frame_size_bytes), 0) FROM outbox_events").fetchone()[0]
            )

        evicted_pending = 0
        while total_bytes + incoming_bytes > self._max_outbox_bytes:
            oldest = conn.execute(
                """
                SELECT event_id, frame_size_bytes
                FROM outbox_events
                WHERE state = 'PENDING'
                ORDER BY created_at ASC, seq_counter ASC
                LIMIT 1
                """
            ).fetchone()
            if oldest is None:
                break
            conn.execute("DELETE FROM outbox_events WHERE event_id = ?", (oldest["event_id"],))
            total_bytes -= int(oldest["frame_size_bytes"])
            evicted_pending += 1

        if evicted_pending > 0:
            logger.warning(
                "Outbox disk quota (%d B) exceeded: evicted %d oldest PENDING event(s) via FIFO ring buffer",
                self._max_outbox_bytes,
                evicted_pending,
            )

    def claim_next_batch(self, limit: int = 10, *, now_ms: int | None = None) -> list[OutboxRecord]:
        """Atomically transition up to limit eligible PENDING events to IN_FLIGHT in FIFO order."""
        ts_ms = int(time.time() * 1000) if now_ms is None else now_ms
        with self._store.write_transaction() as conn:
            rows = conn.execute(
                """
                SELECT event_id, seq_counter, wire_frame, frame_size_bytes, attempt_count, created_at
                FROM outbox_events
                WHERE state = 'PENDING' AND next_retry_at <= ?
                ORDER BY seq_counter ASC
                LIMIT ?
                """,
                (ts_ms, limit),
            ).fetchall()

            records: list[OutboxRecord] = []
            for r in rows:
                next_attempt = int(r["attempt_count"]) + 1
                conn.execute(
                    "UPDATE outbox_events SET state = 'IN_FLIGHT', attempt_count = ? WHERE event_id = ?",
                    (next_attempt, r["event_id"]),
                )
                records.append(
                    OutboxRecord(
                        event_id=str(r["event_id"]),
                        seq_counter=int(r["seq_counter"]),
                        wire_frame=bytes(r["wire_frame"]),
                        frame_size_bytes=int(r["frame_size_bytes"]),
                        attempt_count=next_attempt,
                        created_at=int(r["created_at"]),
                    )
                )
            return records

    def mark_acked(self, event_id: str) -> bool:
        """Mark an outbox event ACKED upon verified Core EVENT_ACK receipt."""
        with self._store.write_transaction() as conn:
            return (
                conn.execute("UPDATE outbox_events SET state = 'ACKED' WHERE event_id = ?", (event_id,)).rowcount
                > 0
            )

    def schedule_retry(
        self,
        event_id: str,
        backoff_ms: int | None = None,
        *,
        now_ms: int | None = None,
    ) -> int:
        """Return an IN_FLIGHT event to PENDING with exponential backoff (1s..60s + jitter)."""
        ts_ms = int(time.time() * 1000) if now_ms is None else now_ms
        with self._store.write_transaction() as conn:
            row = conn.execute(
                "SELECT attempt_count FROM outbox_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                return 0

            if backoff_ms is None:
                attempt = max(1, int(row["attempt_count"]))
                raw_delay = min(_MAX_BACKOFF_MS, _BASE_BACKOFF_MS * (2 ** (attempt - 1)))
                delay_ms = int(min(_MAX_BACKOFF_MS, raw_delay * random.uniform(0.85, 1.15)))
            else:
                delay_ms = max(0, int(backoff_ms))

            conn.execute(
                "UPDATE outbox_events SET state = 'PENDING', next_retry_at = ? WHERE event_id = ?",
                (ts_ms + delay_ms, event_id),
            )
            return delay_ms

    def requeue_all_in_flight(self, *, now_ms: int | None = None) -> int:
        """Reset all IN_FLIGHT rows to PENDING after crash recovery or WebSocket disconnect."""
        ts_ms = int(time.time() * 1000) if now_ms is None else now_ms
        with self._store.write_transaction() as conn:
            return int(
                conn.execute(
                    "UPDATE outbox_events SET state = 'PENDING', next_retry_at = ? WHERE state = 'IN_FLIGHT'",
                    (ts_ms,),
                ).rowcount
            )

    def get_stats(self) -> OutboxStats:
        """Return live outbox depth, byte usage, and node sequence state."""
        session_epoch, last_seq = self._store.read_sequence_state()
        with self._store.lock:
            conn = self._store.connection
            pending = int(
                conn.execute("SELECT COUNT(*) FROM outbox_events WHERE state = 'PENDING'").fetchone()[0]
            )
            in_flight = int(
                conn.execute("SELECT COUNT(*) FROM outbox_events WHERE state = 'IN_FLIGHT'").fetchone()[0]
            )
            total_bytes = int(
                conn.execute(
                    "SELECT COALESCE(SUM(frame_size_bytes), 0) FROM outbox_events WHERE state != 'ACKED'"
                ).fetchone()[0]
            )
        return OutboxStats(
            pending_count=pending,
            in_flight_count=in_flight,
            total_bytes=total_bytes,
            last_seq_counter=last_seq,
            session_epoch=session_epoch,
        )

    def checkpoint_and_close(self) -> None:
        """Flush SQLite WAL to main DB file and close the connection cleanly."""
        self._store.checkpoint_and_close()
