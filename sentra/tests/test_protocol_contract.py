"""Phase 1 Adversarial Verification & Contract Test Suite for SENTRA v1."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import struct
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from sentra_protocol import (
    AAD_SIZE,
    HEADER_SIZE,
    MAX_PAYLOAD_SIZE,
    MAX_PLAINTEXT_SIZE,
    PROTOCOL_MAGIC,
    PROTOCOL_VERSION,
    AuthenticationError,
    DecryptedIntrusionEvent,
    EventAckPayload,
    FenceAckPayload,
    FenceSyncPayload,
    HeartbeatPayload,
    IntegrityError,
    IntrusionEventMetadata,
    InvalidKeyError,
    MalformedFrameError,
    MessageType,
    OversizedFrameError,
    ReplayError,
    TruncatedFrameError,
    UnknownMessageTypeError,
    UnsupportedVersionError,
    VirtualFencePolygon,
    derive_nonce,
    open_frame,
    pack_header,
    pack_intrusion_container,
    seal_control_frame,
    seal_intrusion_event,
    unpack_frame,
    validate_replay_watermark,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTBOX_SCHEMA_PATH = REPO_ROOT / "edge" / "db" / "outbox_schema.sql"
PG_MIGRATION_PATH = REPO_ROOT / "core" / "db" / "migrations" / "001_initial_schema.sql"


def _flip_bit(data: bytes, byte_index: int, bit_mask: int = 0x01) -> bytes:
    mutated = bytearray(data)
    mutated[byte_index] ^= bit_mask
    return bytes(mutated)


def _sample_key_resolver(expected_node_id: UUID, expected_key_id: int, key: bytes):
    def _resolve(node_id: UUID, key_id: int) -> bytes:
        if node_id == expected_node_id and key_id == expected_key_id:
            return key
        raise InvalidKeyError(f"Unknown key for {node_id}:{key_id}")

    return _resolve


def _make_sample_intrusion_frame() -> tuple[bytes, dict[str, object]]:
    node_id = uuid4()
    event_id = uuid4()
    fence_id = uuid4()
    key_id = 7
    session_epoch = 2
    seq_counter = 1042
    timestamp_ns = 1_764_265_000_123_456_789
    key = os.urandom(32)
    wide_bytes = b"\x52\x49\x46\x46" + os.urandom(2048)
    roi_bytes = b"\x52\x49\x46\x46" + os.urandom(512)

    raw_frame = seal_intrusion_event(
        node_id=node_id,
        key_id=key_id,
        session_epoch=session_epoch,
        seq_counter=seq_counter,
        key=key,
        event_id=event_id,
        fence_id=fence_id,
        fence_version=3,
        confidence=0.94,
        bbox=(0.42, 0.31, 0.14, 0.48),
        ground_point=(0.49, 0.79),
        persistence_frames=3,
        wide_bytes=wide_bytes,
        roi_bytes=roi_bytes,
        image_format="webp",
        timestamp_ns=timestamp_ns,
    )

    ctx: dict[str, object] = {
        "node_id": node_id,
        "event_id": event_id,
        "fence_id": fence_id,
        "key_id": key_id,
        "session_epoch": session_epoch,
        "seq_counter": seq_counter,
        "timestamp_ns": timestamp_ns,
        "key": key,
        "wide_bytes": wide_bytes,
        "roi_bytes": roi_bytes,
    }
    return raw_frame, ctx


# -----------------------------------------------------------------------------
# 1. Full Round-Trip Tests (INTRUSION_EVENT & Control Frames)
# -----------------------------------------------------------------------------


def test_intrusion_event_round_trip_and_sha256_verification() -> None:
    raw_frame, ctx = _make_sample_intrusion_frame()
    node_id = ctx["node_id"]
    key_id = ctx["key_id"]
    key = ctx["key"]
    wide_bytes = ctx["wide_bytes"]
    roi_bytes = ctx["roi_bytes"]
    assert isinstance(node_id, UUID)
    assert isinstance(key_id, int)
    assert isinstance(key, bytes)
    assert isinstance(wide_bytes, bytes)
    assert isinstance(roi_bytes, bytes)

    parsed = unpack_frame(raw_frame)
    assert HEADER_SIZE == 58
    assert AAD_SIZE == 42
    assert len(parsed.aad) == 42
    assert parsed.header.magic == PROTOCOL_MAGIC
    assert parsed.header.version == PROTOCOL_VERSION
    assert parsed.header.msg_type is MessageType.INTRUSION_EVENT
    assert parsed.header.node_id == node_id
    assert parsed.header.key_id == key_id
    assert parsed.header.seq_counter == ctx["seq_counter"]
    assert parsed.header.timestamp_ns == ctx["timestamp_ns"]

    decrypted = open_frame(raw_frame, _sample_key_resolver(node_id, key_id, key))
    assert decrypted.session_epoch == ctx["session_epoch"]
    assert isinstance(decrypted.payload, DecryptedIntrusionEvent)
    assert decrypted.payload.wide_bytes == wide_bytes
    assert decrypted.payload.roi_bytes == roi_bytes
    assert decrypted.payload.metadata.event_id == ctx["event_id"]
    assert decrypted.payload.metadata.fence_id == ctx["fence_id"]
    assert decrypted.payload.metadata.fence_version == 3
    assert decrypted.payload.metadata.persistence_frames == 3
    assert decrypted.payload.metadata.image_format == "webp"
    assert decrypted.payload.metadata.wide_sha256 == hashlib.sha256(wide_bytes).hexdigest()
    assert decrypted.payload.metadata.roi_sha256 == hashlib.sha256(roi_bytes).hexdigest()


def test_control_frames_round_trip() -> None:
    node_id = uuid4()
    key = os.urandom(32)
    resolver = _sample_key_resolver(node_id, 1, key)

    cases: list[tuple[MessageType, EventAckPayload | HeartbeatPayload | FenceSyncPayload | FenceAckPayload]] = [
        (
            MessageType.EVENT_ACK,
            EventAckPayload(
                event_id=uuid4(),
                seq_counter=10,
                status="ACCEPTED",
                received_at_ns=time.time_ns(),
            ),
        ),
        (
            MessageType.HEARTBEAT,
            HeartbeatPayload(
                uptime_s=86_400,
                outbox_depth=4,
                outbox_bytes=128_000,
                active_fence_version=2,
                cpu_temp_c=48.5,
            ),
        ),
        (
            MessageType.FENCE_SYNC,
            FenceSyncPayload(
                fence_id=uuid4(),
                version=2,
                name="North Gate Perimeter",
                vertices=[(0.1, 0.2), (0.8, 0.2), (0.85, 0.9), (0.15, 0.85)],
                is_active=True,
            ),
        ),
        (
            MessageType.FENCE_ACK,
            FenceAckPayload(
                fence_id=uuid4(),
                version=2,
                applied=True,
                error=None,
            ),
        ),
    ]

    for idx, (msg_type, payload) in enumerate(cases, start=1):
        frame = seal_control_frame(
            msg_type=msg_type,
            node_id=node_id,
            key_id=1,
            session_epoch=1,
            seq_counter=idx,
            key=key,
            payload=payload,
        )
        opened = open_frame(frame, resolver)
        assert opened.header.msg_type is msg_type
        assert opened.payload == payload


# -----------------------------------------------------------------------------
# 2. Adversarial AAD, Ciphertext, Tag, Key & Digest Tampering Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "byte_offset"),
    [
        ("node_id", 6),
        ("node_id_tail", 21),
        ("key_id", 25),
        ("seq_counter", 33),
        ("timestamp_ns", 41),
    ],
)
def test_aad_tampering_fails_authentication(field_name: str, byte_offset: int) -> None:
    """Flipping 1 bit in any authenticated header field (node_id, key_id, seq_counter, timestamp_ns)
    MUST invalidate the AES-256-GCM authentication tag."""
    raw_frame, ctx = _make_sample_intrusion_frame()
    key = ctx["key"]
    assert isinstance(key, bytes)

    # Resolver returns the real key regardless of tampered header identity/key_id
    # so we specifically test cryptographic AAD verification rather than lookup rejection.
    tampered = _flip_bit(raw_frame, byte_offset)
    with pytest.raises(AuthenticationError, match=r"AES-256-GCM authentication failed"):
        open_frame(tampered, lambda _nid, _kid: key)


def test_ciphertext_bit_flip_fails_authentication() -> None:
    raw_frame, ctx = _make_sample_intrusion_frame()
    node_id = ctx["node_id"]
    key_id = ctx["key_id"]
    key = ctx["key"]
    assert isinstance(node_id, UUID) and isinstance(key_id, int) and isinstance(key, bytes)

    # Flip 1 bit inside encrypted payload ciphertext (offset HEADER_SIZE + 12)
    tampered = _flip_bit(raw_frame, HEADER_SIZE + 12)
    with pytest.raises(AuthenticationError):
        open_frame(tampered, _sample_key_resolver(node_id, key_id, key))


def test_gcm_tag_bit_flip_fails_authentication() -> None:
    raw_frame, ctx = _make_sample_intrusion_frame()
    node_id = ctx["node_id"]
    key_id = ctx["key_id"]
    key = ctx["key"]
    assert isinstance(node_id, UUID) and isinstance(key_id, int) and isinstance(key, bytes)

    # Flip 1 bit in the trailing 16-byte GCM authentication tag (last byte)
    tampered = _flip_bit(raw_frame, len(raw_frame) - 1)
    with pytest.raises(AuthenticationError):
        open_frame(tampered, _sample_key_resolver(node_id, key_id, key))


def test_wrong_key_rejection() -> None:
    raw_frame, ctx = _make_sample_intrusion_frame()
    wrong_key = os.urandom(32)
    while wrong_key == ctx["key"]:
        wrong_key = os.urandom(32)

    with pytest.raises(AuthenticationError):
        open_frame(raw_frame, lambda _nid, _kid: wrong_key)

    with pytest.raises(InvalidKeyError):
        open_frame(raw_frame, lambda _nid, _kid: b"too-short-key")


def test_chain_of_custody_sha256_mismatch_rejected() -> None:
    """Even if an attacker compromises a node key and re-seals a frame with corrupted
    media bytes that do not match the metadata SHA-256 digest, open_frame MUST reject it."""
    node_id = uuid4()
    key = os.urandom(32)
    wide_bytes = b"valid-wide-frame-bytes"
    roi_bytes = b"valid-roi-crop-bytes"

    metadata = IntrusionEventMetadata(
        event_id=uuid4(),
        fence_id=uuid4(),
        fence_version=1,
        confidence=0.91,
        bbox=(0.1, 0.1, 0.2, 0.3),
        ground_point=(0.2, 0.4),
        persistence_frames=3,
        wide_sha256=hashlib.sha256(wide_bytes).hexdigest(),
        roi_sha256=hashlib.sha256(b"different-roi-bytes").hexdigest(),  # mismatched digest
        image_format="jpeg",
    )
    plaintext = pack_intrusion_container(
        metadata.model_dump_json().encode("utf-8"),
        wide_bytes,
        roi_bytes,
    )
    nonce = derive_nonce(1, 55)
    header_bytes = pack_header(
        msg_type=MessageType.INTRUSION_EVENT,
        node_id=node_id,
        key_id=1,
        seq_counter=55,
        timestamp_ns=time.time_ns(),
        nonce=nonce,
        payload_len=len(plaintext) + 16,
    )
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, plaintext, header_bytes[:AAD_SIZE])
    forged_frame = header_bytes + ciphertext_and_tag

    with pytest.raises(IntegrityError, match=r"roi_bytes SHA-256"):
        open_frame(forged_frame, _sample_key_resolver(node_id, 1, key))


# -----------------------------------------------------------------------------
# 3. DoS & Framing Bounds Protection Tests
# -----------------------------------------------------------------------------


def test_truncated_and_malformed_frames_rejected() -> None:
    raw_frame, ctx = _make_sample_intrusion_frame()
    key = ctx["key"]
    assert isinstance(key, bytes)

    # Shorter than 58-byte header
    with pytest.raises(TruncatedFrameError):
        open_frame(raw_frame[: HEADER_SIZE - 1], lambda _n, _k: key)

    # Truncated inside payload
    with pytest.raises(TruncatedFrameError):
        open_frame(raw_frame[:-5], lambda _n, _k: key)

    # Trailing garbage bytes
    with pytest.raises(MalformedFrameError):
        open_frame(raw_frame + b"\x00", lambda _n, _k: key)

    # Corrupted magic bytes
    bad_magic = b"NOPE" + raw_frame[4:]
    with pytest.raises(MalformedFrameError, match=r"Invalid protocol magic"):
        open_frame(bad_magic, lambda _n, _k: key)

    # Unsupported protocol version
    bad_version = raw_frame[:4] + bytes([0x99]) + raw_frame[5:]
    with pytest.raises(UnsupportedVersionError):
        open_frame(bad_version, lambda _n, _k: key)

    # Unknown message type
    bad_msg_type = raw_frame[:5] + bytes([0xFF]) + raw_frame[6:]
    with pytest.raises(UnknownMessageTypeError):
        open_frame(bad_msg_type, lambda _n, _k: key)


def test_oversized_frame_dos_protection() -> None:
    node_id = uuid4()
    nonce = derive_nonce(1, 1)

    # Crafted header advertising payload_len > 10 MiB MUST fail immediately
    oversized_header = struct.pack(
        "!4sBB16sIQQ12sI",
        PROTOCOL_MAGIC,
        PROTOCOL_VERSION,
        int(MessageType.INTRUSION_EVENT),
        node_id.bytes,
        1,
        1,
        time.time_ns(),
        nonce,
        MAX_PAYLOAD_SIZE + 1,
    )
    with pytest.raises(OversizedFrameError):
        unpack_frame(oversized_header + b"\x00" * 32)

    # Sealing an oversized image buffer MUST fail before encryption
    with pytest.raises(OversizedFrameError):
        seal_intrusion_event(
            node_id=node_id,
            key_id=1,
            session_epoch=1,
            seq_counter=1,
            key=os.urandom(32),
            event_id=uuid4(),
            fence_id=uuid4(),
            fence_version=1,
            confidence=0.95,
            bbox=(0.1, 0.1, 0.2, 0.2),
            ground_point=(0.2, 0.3),
            persistence_frames=3,
            wide_bytes=b"\xff" * (MAX_PLAINTEXT_SIZE + 1),
            roi_bytes=b"\xff" * 16,
        )


# -----------------------------------------------------------------------------
# 4. Replay Watermark Protection Tests
# -----------------------------------------------------------------------------


def test_replay_watermark_enforcement() -> None:
    # Fresh monotonic sequence advances watermark
    assert validate_replay_watermark(
        incoming_epoch=1, incoming_seq=11, last_epoch=1, last_seq=10
    ) is True

    # Replay of same or older seq_counter without known duplicate event_id fails
    with pytest.raises(ReplayError):
        validate_replay_watermark(
            incoming_epoch=1, incoming_seq=10, last_epoch=1, last_seq=10
        )

    with pytest.raises(ReplayError):
        validate_replay_watermark(
            incoming_epoch=1, incoming_seq=5, last_epoch=1, last_seq=10
        )

    # Idempotent retry of a known event_id returns False cleanly
    assert (
        validate_replay_watermark(
            incoming_epoch=1,
            incoming_seq=10,
            last_epoch=1,
            last_seq=10,
            is_known_duplicate_event=True,
        )
        is False
    )

    # Stale epoch rejected
    with pytest.raises(ReplayError):
        validate_replay_watermark(
            incoming_epoch=1, incoming_seq=999, last_epoch=2, last_seq=1
        )

    # New session_epoch resets seq cleanly
    assert validate_replay_watermark(
        incoming_epoch=2, incoming_seq=1, last_epoch=1, last_seq=5000
    ) is True


# -----------------------------------------------------------------------------
# 5. Virtual Fence Polygon Validation Tests
# -----------------------------------------------------------------------------


def test_polygon_validation_accepts_valid_3_to_12_vertex_polygons() -> None:
    triangle = VirtualFencePolygon(vertices=[(0.1, 0.1), (0.9, 0.1), (0.5, 0.8)])
    assert len(triangle.vertices) == 3

    # Regular 12-gon inscribed in [0.1, 0.9]
    import math

    dodecagon_pts = [
        (0.5 + 0.35 * math.cos(2 * math.pi * k / 12), 0.5 + 0.35 * math.sin(2 * math.pi * k / 12))
        for k in range(12)
    ]
    dodecagon = VirtualFencePolygon(vertices=dodecagon_pts)
    assert len(dodecagon.vertices) == 12


def test_polygon_validation_rejects_invalid_counts_bounds_and_degenerate_shapes() -> None:
    # Too few vertices (< 3)
    with pytest.raises(ValidationError):
        VirtualFencePolygon(vertices=[(0.1, 0.1), (0.9, 0.9)])

    # Too many vertices (> 12)
    with pytest.raises(ValidationError):
        VirtualFencePolygon(vertices=[(0.1 + i * 0.01, 0.2) for i in range(13)])

    # Out-of-bounds coordinates (< 0.0 and > 1.0)
    with pytest.raises(ValidationError):
        VirtualFencePolygon(vertices=[(-0.05, 0.2), (0.5, 0.2), (0.5, 0.8)])

    with pytest.raises(ValidationError):
        VirtualFencePolygon(vertices=[(0.1, 0.2), (1.05, 0.2), (0.5, 0.8)])

    # Collinear / zero-area degenerate polygon
    with pytest.raises(ValidationError):
        VirtualFencePolygon(vertices=[(0.1, 0.1), (0.5, 0.5), (0.9, 0.9)])

    # Self-intersecting bowtie polygon
    with pytest.raises(ValidationError):
        VirtualFencePolygon(vertices=[(0.1, 0.1), (0.9, 0.9), (0.9, 0.1), (0.1, 0.9)])


# -----------------------------------------------------------------------------
# 6. SQLite WAL Outbox & PostgreSQL 16 Migration Schema Verification
# -----------------------------------------------------------------------------


def test_edge_sqlite_wal_schema_execution_and_constraints(tmp_path: Path) -> None:
    schema_sql = OUTBOX_SCHEMA_PATH.read_text(encoding="utf-8")
    db_file = tmp_path / "wal_outbox.db"

    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(schema_sql)

        # Verify WAL mode, FULL synchronous, and foreign keys enabled
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys;").fetchone()[0]

        assert str(journal_mode).lower() == "wal"
        assert synchronous == 2  # FULL
        assert foreign_keys == 1

        # Verify node_state singleton enforcement
        node_id = str(uuid4())
        now_ms = int(time.time() * 1000)
        conn.execute(
            """
            INSERT INTO node_state (singleton_id, node_id, key_id, session_epoch, last_seq_counter, updated_at)
            VALUES (1, ?, 1, 1, 0, ?)
            """,
            (node_id, now_ms),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO node_state (singleton_id, node_id, key_id, session_epoch, last_seq_counter, updated_at)
                VALUES (2, ?, 1, 1, 0, ?)
                """,
                (node_id, now_ms),
            )

        # Store a real sealed wire frame in outbox_events
        raw_frame, ctx = _make_sample_intrusion_frame()
        event_id = str(ctx["event_id"])
        seq_counter = ctx["seq_counter"]
        assert isinstance(seq_counter, int)

        conn.execute(
            """
            INSERT INTO outbox_events (
                event_id, seq_counter, state, wire_frame, frame_size_bytes, attempt_count, next_retry_at, created_at
            ) VALUES (?, ?, 'PENDING', ?, ?, 0, ?, ?)
            """,
            (event_id, seq_counter, raw_frame, len(raw_frame), now_ms, now_ms),
        )

        # Enforce UNIQUE seq_counter
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO outbox_events (
                    event_id, seq_counter, state, wire_frame, frame_size_bytes, attempt_count, next_retry_at, created_at
                ) VALUES (?, ?, 'PENDING', ?, ?, 0, ?, ?)
                """,
                (str(uuid4()), seq_counter, raw_frame, len(raw_frame), now_ms, now_ms),
            )

        # Enforce CHECK constraint on state enum
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO outbox_events (
                    event_id, seq_counter, state, wire_frame, frame_size_bytes, attempt_count, next_retry_at, created_at
                ) VALUES (?, ?, 'INVALID_STATE', ?, ?, 0, ?, ?)
                """,
                (str(uuid4()), seq_counter + 1, raw_frame, len(raw_frame), now_ms, now_ms),
            )

        # Verify FIFO drain query plan uses idx_outbox_fifo_drain
        plan_rows = conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT event_id, wire_frame
            FROM outbox_events
            WHERE state = 'PENDING' AND next_retry_at <= ?
            ORDER BY seq_counter ASC
            LIMIT 10
            """,
            (now_ms,),
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan_rows)
        assert "idx_outbox_fifo_drain" in plan_text

        # Verify cached_fences accepts valid JSON polygon and rejects malformed JSON
        conn.execute(
            """
            INSERT INTO cached_fences (fence_id, version, name, vertices_json, is_active, synced_at)
            VALUES (?, 1, 'Main Entrance', ?, 1, ?)
            """,
            (str(uuid4()), json.dumps([[0.1, 0.2], [0.8, 0.2], [0.5, 0.9]]), now_ms),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO cached_fences (fence_id, version, name, vertices_json, is_active, synced_at)
                VALUES (?, 2, 'Broken', '{not-valid-json', 1, ?)
                """,
                (str(uuid4()), now_ms),
            )
    finally:
        conn.close()


def test_core_postgres_migration_schema_contract() -> None:
    sql = PG_MIGRATION_PATH.read_text(encoding="utf-8")
    for required_fragment in (
        "CREATE EXTENSION IF NOT EXISTS citext;",
        "CREATE TABLE users",
        "CHECK (role IN ('ADMIN', 'OPERATOR', 'AUDITOR'))",
        "CREATE TABLE refresh_tokens",
        "CREATE TABLE edge_nodes",
        "CREATE TABLE virtual_fences",
        "jsonb_typeof(vertices) = 'array'",
        "jsonb_array_length(vertices) BETWEEN 3 AND 12",
        "UNIQUE (node_id, version)",
        "CREATE TABLE intrusion_events",
        "CHECK (triage_status IN ('NEW', 'ACKNOWLEDGED', 'FALSE_POSITIVE', 'ESCALATED'))",
        "CREATE TABLE audit_logs",
        "BEFORE UPDATE OR DELETE ON audit_logs",
        "prevent_audit_log_mutation",
    ):
        assert required_fragment in sql, f"Missing required PostgreSQL DDL fragment: {required_fragment}"
