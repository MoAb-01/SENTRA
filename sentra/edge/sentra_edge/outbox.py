"""Thread-safe SQLite WAL transactional outbox, monotonic sequence counter & fence cache."""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sentra_protocol.crypto import seal_intrusion_event
from sentra_protocol.models import ImageFormat, NormalizedBBox, NormalizedPoint

from .geofence import FencePolygon

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_PATH: Path = Path(__file__).resolve().parents[1] / "db" / "outbox_schema.sql"
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
    """Crash-safe SQLite WAL outbox with atomic sequence persistence and ring-buffer eviction."""

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
        self._db_path = db_path
        self._node_id = node_id
        self._key_id = key_id
        self._encryption_key = encryption_key
        self._max_outbox_bytes = max_outbox_bytes
        self._lock = threading.RLock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path),
            isolation_level=None,  # Explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row

        schema_sql = schema_path.read_text(encoding="utf-8")
        self._conn.executescript(schema_sql)
        self._init_node_state_and_recover()

    def _init_node_state_and_recover(self) -> None:
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT node_id, key_id, session_epoch, last_seq_counter FROM node_state WHERE singleton_id = 1"
                ).fetchone()
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO node_state (singleton_id, node_id, key_id, session_epoch, last_seq_counter, updated_at)
                        VALUES (1, ?, ?, 1, 0, ?)
                        """,
                        (str(self._node_id), self._key_id, now_ms),
                    )
                else:
                    if row["node_id"] != str(self._node_id):
                        raise ValueError(
                            f"Database belongs to node_id={row['node_id']}, refusing boot as {self._node_id}"
                        )
                    if row["key_id"] != self._key_id:
                        new_epoch = int(row["session_epoch"]) + 1
                        self._conn.execute(
                            "UPDATE node_state SET key_id = ?, session_epoch = ?, updated_at = ? WHERE singleton_id = 1",
                            (self._key_id, new_epoch, now_ms),
                        )

                # Crash recovery: return any stranded IN_FLIGHT events to PENDING
                recovered = self._conn.execute(
                    "UPDATE outbox_events SET state = 'PENDING', next_retry_at = ? WHERE state = 'IN_FLIGHT'",
                    (now_ms,),
                ).rowcount
                self._conn.execute("COMMIT")
                if recovered > 0:
                    logger.warning("Recovered %d stranded IN_FLIGHT outbox rows to PENDING", recovered)
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def allocate_control_seq(self) -> tuple[int, int]:
        """Atomically allocate the next (session_epoch, seq_counter) for signed control frames."""
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT session_epoch, last_seq_counter FROM node_state WHERE singleton_id = 1"
                ).fetchone()
                next_seq = int(row["last_seq_counter"]) + 1
                epoch = int(row["session_epoch"])
                self._conn.execute(
                    "UPDATE node_state SET last_seq_counter = ?, updated_at = ? WHERE singleton_id = 1",
                    (next_seq, now_ms),
                )
                self._conn.execute("COMMIT")
                return epoch, next_seq
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

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

        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT session_epoch, last_seq_counter FROM node_state WHERE singleton_id = 1"
                ).fetchone()
                session_epoch = int(row["session_epoch"])
                seq = int(row["last_seq_counter"]) + 1

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

                self._enforce_ring_buffer_quota(incoming_bytes=frame_size)

                self._conn.execute(
                    "UPDATE node_state SET last_seq_counter = ?, updated_at = ? WHERE singleton_id = 1",
                    (seq, now_ms),
                )
                self._conn.execute(
                    """
                    INSERT INTO outbox_events (
                        event_id, seq_counter, state, wire_frame, frame_size_bytes,
                        attempt_count, next_retry_at, created_at
                    ) VALUES (?, ?, 'PENDING', ?, ?, 0, ?, ?)
                    """,
                    (str(event_id), seq, wire_frame, frame_size, now_ms, now_ms),
                )
                self._conn.execute("COMMIT")
                return OutboxRecord(
                    event_id=str(event_id),
                    seq_counter=seq,
                    wire_frame=wire_frame,
                    frame_size_bytes=frame_size,
                    attempt_count=0,
                    created_at=now_ms,
                )
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _enforce_ring_buffer_quota(self, incoming_bytes: int) -> None:
        """Evict ACKED rows first, then oldest PENDING rows (FIFO) until quota permits insert."""
        total_bytes = int(
            self._conn.execute(
                "SELECT COALESCE(SUM(frame_size_bytes), 0) FROM outbox_events"
            ).fetchone()[0]
        )
        if total_bytes + incoming_bytes <= self._max_outbox_bytes:
            return

        # Purge already-ACKED rows first to avoid dropping unsent telemetry unnecessarily
        acked_freed = self._conn.execute(
            "DELETE FROM outbox_events WHERE state = 'ACKED'"
        ).rowcount
        if acked_freed > 0:
            total_bytes = int(
                self._conn.execute(
                    "SELECT COALESCE(SUM(frame_size_bytes), 0) FROM outbox_events"
                ).fetchone()[0]
            )

        evicted_pending = 0
        while total_bytes + incoming_bytes > self._max_outbox_bytes:
            oldest = self._conn.execute(
                """
                SELECT event_id, frame_size_bytes, seq_counter
                FROM outbox_events
                WHERE state = 'PENDING'
                ORDER BY created_at ASC, seq_counter ASC
                LIMIT 1
                """
            ).fetchone()
            if oldest is None:
                break
            self._conn.execute(
                "DELETE FROM outbox_events WHERE event_id = ?", (oldest["event_id"],)
            )
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
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
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
                    self._conn.execute(
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
                self._conn.execute("COMMIT")
                return records
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def mark_acked(self, event_id: str) -> bool:
        """Mark an outbox event ACKED upon verified Core EVENT_ACK receipt."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                updated = self._conn.execute(
                    "UPDATE outbox_events SET state = 'ACKED' WHERE event_id = ?",
                    (event_id,),
                ).rowcount
                self._conn.execute("COMMIT")
                return updated > 0
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def schedule_retry(
        self,
        event_id: str,
        backoff_ms: int | None = None,
        *,
        now_ms: int | None = None,
    ) -> int:
        """Return an IN_FLIGHT event to PENDING with exponential backoff (1s..60s + jitter)."""
        ts_ms = int(time.time() * 1000) if now_ms is None else now_ms
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT attempt_count FROM outbox_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return 0

                if backoff_ms is None:
                    attempt = max(1, int(row["attempt_count"]))
                    raw_delay = min(_MAX_BACKOFF_MS, _BASE_BACKOFF_MS * (2 ** (attempt - 1)))
                    jitter = random.uniform(0.85, 1.15)
                    delay_ms = int(min(_MAX_BACKOFF_MS, raw_delay * jitter))
                else:
                    delay_ms = max(0, int(backoff_ms))

                next_retry_at = ts_ms + delay_ms
                self._conn.execute(
                    "UPDATE outbox_events SET state = 'PENDING', next_retry_at = ? WHERE event_id = ?",
                    (next_retry_at, event_id),
                )
                self._conn.execute("COMMIT")
                return delay_ms
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def requeue_all_in_flight(self, *, now_ms: int | None = None) -> int:
        """Reset all IN_FLIGHT rows to PENDING after a WebSocket disconnect."""
        ts_ms = int(time.time() * 1000) if now_ms is None else now_ms
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                count = self._conn.execute(
                    "UPDATE outbox_events SET state = 'PENDING', next_retry_at = ? WHERE state = 'IN_FLIGHT'",
                    (ts_ms,),
                ).rowcount
                self._conn.execute("COMMIT")
                return count
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def save_fences(self, fences: Sequence[FencePolygon]) -> None:
        """Persist synced virtual fences to cached_fences for offline cold-start boot."""
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("DELETE FROM cached_fences")
                for fence in fences:
                    vertices_list = [[float(x), float(y)] for x, y in fence.vertices.tolist()]
                    self._conn.execute(
                        """
                        INSERT INTO cached_fences (fence_id, version, name, vertices_json, is_active, synced_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(fence.fence_id),
                            fence.version,
                            fence.name,
                            json.dumps(vertices_list),
                            1 if fence.is_active else 0,
                            now_ms,
                        ),
                    )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def load_cached_fences(self) -> list[FencePolygon]:
        """Load persisted virtual fences from SQLite so enforcement works offline at boot."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT fence_id, version, name, vertices_json, is_active
                FROM cached_fences
                WHERE is_active = 1
                ORDER BY version DESC
                """
            ).fetchall()

        fences: list[FencePolygon] = []
        for row in rows:
            raw_verts = json.loads(row["vertices_json"])
            vertices = [(float(pt[0]), float(pt[1])) for pt in raw_verts]
            fences.append(
                FencePolygon.from_vertices(
                    fence_id=UUID(str(row["fence_id"])),
                    version=int(row["version"]),
                    name=str(row["name"]),
                    vertices=vertices,
                    is_active=bool(row["is_active"]),
                )
            )
        return fences

    def get_stats(self) -> OutboxStats:
        """Return live outbox depth, byte usage, and node sequence state."""
        with self._lock:
            ns = self._conn.execute(
                "SELECT session_epoch, last_seq_counter FROM node_state WHERE singleton_id = 1"
            ).fetchone()
            pending = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM outbox_events WHERE state = 'PENDING'"
                ).fetchone()[0]
            )
            in_flight = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM outbox_events WHERE state = 'IN_FLIGHT'"
                ).fetchone()[0]
            )
            total_bytes = int(
                self._conn.execute(
                    "SELECT COALESCE(SUM(frame_size_bytes), 0) FROM outbox_events WHERE state != 'ACKED'"
                ).fetchone()[0]
            )
        return OutboxStats(
            pending_count=pending,
            in_flight_count=in_flight,
            total_bytes=total_bytes,
            last_seq_counter=int(ns["last_seq_counter"]),
            session_epoch=int(ns["session_epoch"]),
        )

    def checkpoint_and_close(self) -> None:
        """Flush SQLite WAL to main DB file and close the connection cleanly."""
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            finally:
                self._conn.close()
