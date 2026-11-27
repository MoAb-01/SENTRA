"""SQLite WAL connection manager, node_state monotonic sequence store & cached fences."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from .geofence import FencePolygon

DEFAULT_SCHEMA_PATH: Path = Path(__file__).resolve().parents[1] / "db" / "outbox_schema.sql"


class EdgeStateStore:
    """Thread-safe SQLite WAL persistence for node_state and offline cached_fences."""

    def __init__(
        self,
        *,
        db_path: Path,
        node_id: UUID,
        key_id: int,
        schema_path: Path = DEFAULT_SCHEMA_PATH,
    ) -> None:
        self._db_path = db_path
        self._node_id = node_id
        self._key_id = key_id
        self._lock = threading.RLock()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path),
            isolation_level=None,  # Explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(schema_path.read_text(encoding="utf-8"))
        self._init_node_state()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        """Acquire RLock and execute a BEGIN IMMEDIATE transaction with safe rollback."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _init_node_state(self) -> None:
        now_ms = int(time.time() * 1000)
        with self.write_transaction() as conn:
            row = conn.execute(
                "SELECT node_id, key_id, session_epoch FROM node_state WHERE singleton_id = 1"
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO node_state (
                        singleton_id, node_id, key_id, session_epoch, last_seq_counter, updated_at
                    ) VALUES (1, ?, ?, 1, 0, ?)
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
                    conn.execute(
                        "UPDATE node_state SET key_id = ?, session_epoch = ?, updated_at = ? WHERE singleton_id = 1",
                        (self._key_id, new_epoch, now_ms),
                    )

    def next_sequence_in_tx(self, conn: sqlite3.Connection, now_ms: int) -> tuple[int, int]:
        """Advance node_state.last_seq_counter inside an active write transaction."""
        row = conn.execute(
            "SELECT session_epoch, last_seq_counter FROM node_state WHERE singleton_id = 1"
        ).fetchone()
        session_epoch = int(row["session_epoch"])
        next_seq = int(row["last_seq_counter"]) + 1
        conn.execute(
            "UPDATE node_state SET last_seq_counter = ?, updated_at = ? WHERE singleton_id = 1",
            (next_seq, now_ms),
        )
        return session_epoch, next_seq

    def allocate_control_seq(self) -> tuple[int, int]:
        """Atomically allocate the next (session_epoch, seq_counter) for control frames."""
        now_ms = int(time.time() * 1000)
        with self.write_transaction() as conn:
            return self.next_sequence_in_tx(conn, now_ms)

    def read_sequence_state(self) -> tuple[int, int]:
        """Return (session_epoch, last_seq_counter)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT session_epoch, last_seq_counter FROM node_state WHERE singleton_id = 1"
            ).fetchone()
        return int(row["session_epoch"]), int(row["last_seq_counter"])

    def save_fences(self, fences: Sequence[FencePolygon]) -> None:
        """Persist synced virtual fences to cached_fences for offline cold-start boot."""
        now_ms = int(time.time() * 1000)
        with self.write_transaction() as conn:
            conn.execute("DELETE FROM cached_fences")
            for fence in fences:
                vertices_list = [[float(x), float(y)] for x, y in fence.vertices.tolist()]
                conn.execute(
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

    def checkpoint_and_close(self) -> None:
        """Flush SQLite WAL to main DB file and close the connection cleanly."""
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            finally:
                self._conn.close()
