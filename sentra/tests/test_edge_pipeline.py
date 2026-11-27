"""Phase 2 Verification, Crash-Recovery, Integration & Latency Benchmark Suite."""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import sqlite3
import time
from pathlib import Path
from uuid import UUID, uuid4

import cv2
import numpy as np
import pytest
import websockets
from sentra_protocol.constants import MessageType
from sentra_protocol.crypto import DecryptedIntrusionEvent, open_frame, seal_control_frame
from sentra_protocol.models import EventAckPayload, FenceAckPayload, FenceSyncPayload, HeartbeatPayload

from sentra_edge.config import load_edge_config
from sentra_edge.detector import (
    Detection,
    decode_yolov8_person_output,
    letterbox_bgr,
)
from sentra_edge.evidence import extract_dual_evidence
from sentra_edge.geofence import AtomicFenceStore, FencePolygon, points_in_polygon_batch
from sentra_edge.outbox import TransactionalOutbox
from sentra_edge.tracker import PersistenceFilter
from sentra_edge.uplink import UplinkWorker


def _make_synthetic_frame(height: int, width: int, fill_value: int) -> np.ndarray:
    frame = np.full((height, width, 3), fill_value, dtype=np.uint8)
    # Add deterministic visual texture so JPEG/WebP compression is realistic
    frame[::16, :, 0] = (fill_value + 40) % 256
    frame[:, ::16, 2] = (fill_value + 80) % 256
    return frame


# -----------------------------------------------------------------------------
# 1. Vectorized Ray-Casting PiP Accuracy & < 1.0 ms Latency Benchmark
# -----------------------------------------------------------------------------


def test_ray_casting_pip_convex_concave_u_l_and_12_vertex_accuracy() -> None:
    # Concave U-shaped polygon (8 vertices) with notch in [0.35, 0.65] x [0.40, 0.90]
    u_poly = np.array(
        [
            [0.10, 0.10],
            [0.90, 0.10],
            [0.90, 0.90],
            [0.65, 0.90],
            [0.65, 0.40],
            [0.35, 0.40],
            [0.35, 0.90],
            [0.10, 0.90],
        ],
        dtype=np.float64,
    )
    u_points = np.array(
        [
            [0.20, 0.70],  # inside left arm -> True
            [0.80, 0.70],  # inside right arm -> True
            [0.50, 0.25],  # inside bottom bridge -> True
            [0.50, 0.65],  # inside concave U notch -> False
            [0.05, 0.50],  # outside left -> False
            [0.95, 0.50],  # outside right -> False
            [0.50, 0.40],  # aligned with horizontal notch edge -> False/safe (no ZeroDivision)
        ],
        dtype=np.float64,
    )
    u_result = points_in_polygon_batch(u_points, u_poly)
    assert u_result[:6].tolist() == [True, True, True, False, False, False]
    assert u_result.dtype == np.bool_

    # Concave L-shaped polygon (6 vertices) with upper-right cutout [0.45, 0.90] x [0.10, 0.55]
    l_poly = np.array(
        [
            [0.10, 0.10],
            [0.45, 0.10],
            [0.45, 0.55],
            [0.90, 0.55],
            [0.90, 0.90],
            [0.10, 0.90],
        ],
        dtype=np.float64,
    )
    l_points = np.array(
        [
            [0.25, 0.30],  # inside vertical arm -> True
            [0.70, 0.75],  # inside horizontal arm -> True
            [0.70, 0.30],  # inside L notch cutout -> False
            [0.02, 0.02],  # exterior -> False
        ],
        dtype=np.float64,
    )
    assert points_in_polygon_batch(l_points, l_poly).tolist() == [True, True, False, False]

    # Regular 12-vertex polygon centered at (0.5, 0.5), radius 0.35
    dodecagon = np.array(
        [
            [0.5 + 0.35 * math.cos(2 * math.pi * k / 12), 0.5 + 0.35 * math.sin(2 * math.pi * k / 12)]
            for k in range(12)
        ],
        dtype=np.float64,
    )
    d_pts = np.array([[0.5, 0.5], [0.7, 0.5], [0.05, 0.05], [0.95, 0.95]], dtype=np.float64)
    assert points_in_polygon_batch(d_pts, dodecagon).tolist() == [True, True, False, False]


def test_ray_casting_pip_benchmark_100_boxes_12_vertices_under_1ms() -> None:
    rng = np.random.default_rng(seed=42)
    polygon_12 = np.array(
        [
            [0.5 + 0.35 * math.cos(2 * math.pi * k / 12), 0.5 + 0.35 * math.sin(2 * math.pi * k / 12)]
            for k in range(12)
        ],
        dtype=np.float64,
    )
    points_100 = rng.uniform(0.0, 1.0, size=(100, 2))

    # Warm-up
    _ = points_in_polygon_batch(points_100, polygon_12)

    iterations = 1_000
    latencies_ms = np.empty(iterations, dtype=np.float64)
    for i in range(iterations):
        t0 = time.perf_counter_ns()
        res = points_in_polygon_batch(points_100, polygon_12)
        latencies_ms[i] = (time.perf_counter_ns() - t0) / 1_000_000.0
        assert res.shape == (100,)

    mean_ms = float(np.mean(latencies_ms))
    p50_ms, p95_ms, p99_ms = [float(x) for x in np.percentile(latencies_ms, [50, 95, 99])]
    print(
        f"\n[PiP Benchmark: 100 boxes x 12-vertex polygon x {iterations} iters] "
        f"mean={mean_ms:.4f}ms p50={p50_ms:.4f}ms p95={p95_ms:.4f}ms p99={p99_ms:.4f}ms"
    )
    assert mean_ms < 1.0, f"Mean PiP latency {mean_ms:.4f}ms exceeded 1.0ms budget"


# -----------------------------------------------------------------------------
# 2. Temporal N>=3 Suppression, Peak-Confidence Selection & Cooldown
# -----------------------------------------------------------------------------


def test_persistence_filter_suppresses_transients_selects_peak_and_enforces_cooldown() -> None:
    fence_id = uuid4()
    tracker = PersistenceFilter(persistence_frames=3, max_miss_frames=0, cooldown_sec=10.0)
    bbox = (0.40, 0.30, 0.15, 0.45)
    bbox_px = (256, 144, 96, 216)

    base_ns = 1_764_265_000_000_000_000
    step_ns = 33_000_000  # ~30 FPS

    # Part A: 2-frame transient false positive followed by empty frame -> 0 triggers
    for i, conf in enumerate([0.72, 0.81]):
        frame = _make_synthetic_frame(120, 160, fill_value=20 + i)
        det = Detection(bbox_norm=bbox, bbox_px=bbox_px, confidence=conf)
        out = tracker.update(
            fence_id=fence_id,
            fence_version=1,
            detections_inside=[det],
            frame_bgr=frame,
            timestamp_ns=base_ns + i * step_ns,
        )
        assert out == []

    # Empty frame resets transient track
    assert (
        tracker.update(
            fence_id=fence_id,
            fence_version=1,
            detections_inside=[],
            frame_bgr=_make_synthetic_frame(120, 160, fill_value=0),
            timestamp_ns=base_ns + 2 * step_ns,
        )
        == []
    )

    # Part B: 3 consecutive frames [0.61, 0.92, 0.74] -> triggers once with frame #2 (0.92)
    f1 = _make_synthetic_frame(120, 160, fill_value=50)
    f2 = _make_synthetic_frame(120, 160, fill_value=123)  # Unique pixel marker for peak frame
    f3 = _make_synthetic_frame(120, 160, fill_value=200)
    f4 = _make_synthetic_frame(120, 160, fill_value=220)

    r1 = tracker.update(
        fence_id=fence_id,
        fence_version=1,
        detections_inside=[Detection(bbox_norm=bbox, bbox_px=bbox_px, confidence=0.61)],
        frame_bgr=f1,
        timestamp_ns=base_ns + 10 * step_ns,
    )
    assert r1 == []

    r2 = tracker.update(
        fence_id=fence_id,
        fence_version=1,
        detections_inside=[Detection(bbox_norm=bbox, bbox_px=bbox_px, confidence=0.92)],
        frame_bgr=f2,
        timestamp_ns=base_ns + 11 * step_ns,
    )
    assert r2 == []

    r3 = tracker.update(
        fence_id=fence_id,
        fence_version=1,
        detections_inside=[Detection(bbox_norm=bbox, bbox_px=bbox_px, confidence=0.74)],
        frame_bgr=f3,
        timestamp_ns=base_ns + 12 * step_ns,
    )
    assert len(r3) == 1
    confirmed = r3[0]
    assert confirmed.confidence == pytest.approx(0.92)
    assert confirmed.persistence_frames == 3
    assert confirmed.detected_at_ns == base_ns + 11 * step_ns
    assert int(confirmed.peak_frame_bgr[1, 1, 1]) == 123  # Exact frame #2 retained

    # Part C: Frame #4 (and #5, #6) during 10s cooldown MUST be suppressed
    for extra_idx in range(13, 17):
        suppressed = tracker.update(
            fence_id=fence_id,
            fence_version=1,
            detections_inside=[Detection(bbox_norm=bbox, bbox_px=bbox_px, confidence=0.95)],
            frame_bgr=f4,
            timestamp_ns=base_ns + extra_idx * step_ns,
        )
        assert suppressed == []


def test_persistence_filter_optional_1_frame_flicker_tolerance() -> None:
    fence_id = uuid4()
    tracker = PersistenceFilter(persistence_frames=3, max_miss_frames=1, cooldown_sec=10.0)
    bbox = (0.30, 0.30, 0.15, 0.40)
    bbox_px = (100, 100, 50, 120)
    frame = _make_synthetic_frame(120, 160, fill_value=90)

    assert tracker.update(fence_id=fence_id, fence_version=1, detections_inside=[Detection(bbox, bbox_px, 0.70)], frame_bgr=frame, timestamp_ns=1_000) == []
    # Single missed frame tolerated
    assert tracker.update(fence_id=fence_id, fence_version=1, detections_inside=[], frame_bgr=frame, timestamp_ns=2_000) == []
    assert tracker.update(fence_id=fence_id, fence_version=1, detections_inside=[Detection(bbox, bbox_px, 0.88)], frame_bgr=frame, timestamp_ns=3_000) == []
    res = tracker.update(fence_id=fence_id, fence_version=1, detections_inside=[Detection(bbox, bbox_px, 0.80)], frame_bgr=frame, timestamp_ns=4_000)
    assert len(res) == 1
    assert res[0].confidence == pytest.approx(0.88)


# -----------------------------------------------------------------------------
# 3. Dual-Perspective Evidence Extraction & Edge Clamping
# -----------------------------------------------------------------------------


def test_dual_evidence_roi_slice_and_edge_clamping() -> None:
    frame = _make_synthetic_frame(720, 1280, fill_value=100)

    # Normal centered box: x=256, y=144, w=256, h=400 -> upper 35% height = 140px
    bundle = extract_dual_evidence(frame, (0.20, 0.20, 0.20, 400 / 720), jpeg_quality=85)
    assert bundle.wide_size == (1280, 720)
    assert bundle.roi_size == (256, 140)
    assert bundle.roi_rect_px == (256, 144, 512, 284)

    decoded_wide = cv2.imdecode(np.frombuffer(bundle.wide_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    decoded_roi = cv2.imdecode(np.frombuffer(bundle.roi_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded_wide is not None and decoded_wide.shape == (720, 1280, 3)
    assert decoded_roi is not None and decoded_roi.shape == (140, 256, 3)

    # Extreme boundary boxes (bottom-right corner & tiny 4px box) must clamp cleanly without errors
    edge_boxes = [
        (0.995, 0.995, 0.005, 0.005),
        (0.0, 0.0, 0.004, 0.004),
        (0.95, 0.0, 0.05, 0.01),
    ]
    for box in edge_boxes:
        clamped = extract_dual_evidence(frame, box, jpeg_quality=80)
        assert clamped.roi_size[0] >= 8 and clamped.roi_size[1] >= 8
        x1, y1, x2, y2 = clamped.roi_rect_px
        assert 0 <= x1 < x2 <= 1280
        assert 0 <= y1 < y2 <= 720
        assert len(clamped.roi_bytes) > 0 and len(clamped.wide_bytes) > 0


# -----------------------------------------------------------------------------
# 4. SQLite WAL Outbox Crash Recovery, Reboot Monotonicity, Backoff & Eviction
# -----------------------------------------------------------------------------


def test_outbox_crash_recovery_reboot_monotonicity_backoff_and_ring_eviction(tmp_path: Path) -> None:
    db_path = tmp_path / "edge_outbox.db"
    node_id = uuid4()
    fence_id = uuid4()
    key = os.urandom(32)
    frame = _make_synthetic_frame(160, 240, fill_value=77)
    ev = extract_dual_evidence(frame, (0.2, 0.2, 0.3, 0.5), jpeg_quality=80)

    # Phase A: Enqueue 2 events and leave event #1 stranded IN_FLIGHT to simulate sudden power loss
    outbox1 = TransactionalOutbox(
        db_path=db_path,
        node_id=node_id,
        key_id=1,
        encryption_key=key,
        max_outbox_bytes=10_000_000,
    )
    r1 = outbox1.enqueue_intrusion(
        event_id=uuid4(),
        fence_id=fence_id,
        fence_version=1,
        confidence=0.91,
        bbox=(0.2, 0.2, 0.3, 0.5),
        ground_point=(0.35, 0.7),
        persistence_frames=3,
        wide_bytes=ev.wide_bytes,
        roi_bytes=ev.roi_bytes,
    )
    r2 = outbox1.enqueue_intrusion(
        event_id=uuid4(),
        fence_id=fence_id,
        fence_version=1,
        confidence=0.88,
        bbox=(0.2, 0.2, 0.3, 0.5),
        ground_point=(0.35, 0.7),
        persistence_frames=3,
        wide_bytes=ev.wide_bytes,
        roi_bytes=ev.roi_bytes,
    )
    assert (r1.seq_counter, r2.seq_counter) == (1, 2)

    claimed = outbox1.claim_next_batch(limit=1)
    assert len(claimed) == 1 and claimed[0].event_id == r1.event_id
    assert outbox1.get_stats().in_flight_count == 1

    # Simulate abrupt crash (close without ACK) and restart on same SQLite file
    outbox1.checkpoint_and_close()

    outbox2 = TransactionalOutbox(
        db_path=db_path,
        node_id=node_id,
        key_id=1,
        encryption_key=key,
        max_outbox_bytes=10_000_000,
    )
    stats_after_boot = outbox2.get_stats()
    assert stats_after_boot.in_flight_count == 0
    assert stats_after_boot.pending_count == 2  # Stranded IN_FLIGHT recovered to PENDING
    assert stats_after_boot.last_seq_counter == 2

    # Next enqueue after reboot strictly continues monotonic seq_counter == 3
    r3 = outbox2.enqueue_intrusion(
        event_id=uuid4(),
        fence_id=fence_id,
        fence_version=1,
        confidence=0.95,
        bbox=(0.2, 0.2, 0.3, 0.5),
        ground_point=(0.35, 0.7),
        persistence_frames=3,
        wide_bytes=ev.wide_bytes,
        roi_bytes=ev.roi_bytes,
    )
    assert r3.seq_counter == 3

    # Test exponential backoff scheduling hides row until next_retry_at
    now_ms = int(time.time() * 1000)
    batch = outbox2.claim_next_batch(limit=1, now_ms=now_ms)
    assert batch[0].event_id == r1.event_id
    delay_ms = outbox2.schedule_retry(r1.event_id, now_ms=now_ms)
    assert 850 <= delay_ms <= 60_000
    # Immediate claim at now_ms should skip r1 and pick r2 next
    next_batch = outbox2.claim_next_batch(limit=1, now_ms=now_ms)
    assert next_batch[0].event_id == r2.event_id

    # Test offline fence persistence round-trip
    poly = FencePolygon.from_vertices(
        fence_id=fence_id,
        version=4,
        name="East Gate",
        vertices=[(0.1, 0.2), (0.8, 0.2), (0.8, 0.9), (0.1, 0.9)],
    )
    outbox2.save_fences([poly])
    reloaded_fences = outbox2.load_cached_fences()
    assert len(reloaded_fences) == 1
    assert reloaded_fences[0].fence_id == fence_id
    assert reloaded_fences[0].version == 4
    outbox2.checkpoint_and_close()

    # Phase B: FIFO Ring-Buffer Disk Quota Eviction (allow room for only 2 frames)
    quota_db = tmp_path / "quota_outbox.db"
    single_frame_size = r1.frame_size_bytes
    quota_cap = int(single_frame_size * 2.4)
    quota_outbox = TransactionalOutbox(
        db_path=quota_db,
        node_id=node_id,
        key_id=1,
        encryption_key=key,
        max_outbox_bytes=quota_cap,
    )
    enqueued_seqs: list[int] = []
    for _ in range(4):
        rec = quota_outbox.enqueue_intrusion(
            event_id=uuid4(),
            fence_id=fence_id,
            fence_version=1,
            confidence=0.90,
            bbox=(0.2, 0.2, 0.3, 0.5),
            ground_point=(0.35, 0.7),
            persistence_frames=3,
            wide_bytes=ev.wide_bytes,
            roi_bytes=ev.roi_bytes,
        )
        enqueued_seqs.append(rec.seq_counter)

    remaining = quota_outbox.claim_next_batch(limit=10)
    remaining_seqs = [rec.seq_counter for rec in remaining]
    assert remaining_seqs == [3, 4]  # Oldest seq 1 and 2 evicted FIFO
    assert sum(rec.frame_size_bytes for rec in remaining) <= quota_cap
    quota_outbox.checkpoint_and_close()


# -----------------------------------------------------------------------------
# 5. End-to-End Sealed Frame Verification (SQLite WAL -> Phase 1 open_frame)
# -----------------------------------------------------------------------------


def test_end_to_end_sqlite_wal_sealed_frame_decrypts_with_phase1_protocol(tmp_path: Path) -> None:
    db_path = tmp_path / "e2e_outbox.db"
    node_id = uuid4()
    fence_id = uuid4()
    event_id = uuid4()
    key_id = 3
    key = os.urandom(32)

    frame = _make_synthetic_frame(480, 640, fill_value=140)
    evidence = extract_dual_evidence(frame, (0.25, 0.20, 0.25, 0.60), jpeg_quality=85, image_format="webp")

    outbox = TransactionalOutbox(
        db_path=db_path,
        node_id=node_id,
        key_id=key_id,
        encryption_key=key,
    )
    record = outbox.enqueue_intrusion(
        event_id=event_id,
        fence_id=fence_id,
        fence_version=2,
        confidence=0.93,
        bbox=(0.25, 0.20, 0.25, 0.60),
        ground_point=(0.375, 0.80),
        persistence_frames=3,
        wide_bytes=evidence.wide_bytes,
        roi_bytes=evidence.roi_bytes,
        image_format=evidence.image_format,
    )
    outbox.checkpoint_and_close()

    # Read raw BLOB directly from SQLite WAL database
    conn = sqlite3.connect(db_path)
    try:
        stored_blob = conn.execute(
            "SELECT wire_frame FROM outbox_events WHERE event_id = ?", (str(event_id),)
        ).fetchone()[0]
    finally:
        conn.close()

    decrypted = open_frame(bytes(stored_blob), lambda nid, kid: key if (nid == node_id and kid == key_id) else b"")
    assert decrypted.header.node_id == node_id
    assert decrypted.header.key_id == key_id
    assert decrypted.header.seq_counter == record.seq_counter
    assert isinstance(decrypted.payload, DecryptedIntrusionEvent)
    assert decrypted.payload.metadata.event_id == event_id
    assert decrypted.payload.metadata.fence_id == fence_id
    assert decrypted.payload.wide_bytes == evidence.wide_bytes
    assert decrypted.payload.roi_bytes == evidence.roi_bytes
    assert decrypted.payload.metadata.wide_sha256 == hashlib.sha256(evidence.wide_bytes).hexdigest()
    assert decrypted.payload.metadata.roi_sha256 == hashlib.sha256(evidence.roi_bytes).hexdigest()


# -----------------------------------------------------------------------------
# 6. Detector Decode/NMS, Config Loader & Async WebSocket Uplink Integration
# -----------------------------------------------------------------------------


def test_yolov8_letterbox_decode_class0_filter_and_nms() -> None:
    frame = _make_synthetic_frame(720, 1280, fill_value=60)
    tensor, transform = letterbox_bgr(frame, target_size=640)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert transform.scale == pytest.approx(0.5)
    assert transform.pad_y == pytest.approx(140.0)

    # Synthetic [1, 84, 8400] YOLOv8 output:
    # anchor 0: person (class 0) high conf 0.91 at center (320, 320), w=100, h=200
    # anchor 1: overlapping person (class 0) lower conf 0.72 -> should be suppressed by NMS
    # anchor 2: car (class 2) high conf 0.98 -> must be ignored (not class 0)
    raw = np.zeros((1, 84, 8400), dtype=np.float32)
    raw[0, 0:4, 0] = [320.0, 320.0, 100.0, 200.0]
    raw[0, 4, 0] = 0.91
    raw[0, 0:4, 1] = [322.0, 321.0, 100.0, 200.0]
    raw[0, 4, 1] = 0.72
    raw[0, 0:4, 2] = [120.0, 250.0, 80.0, 80.0]
    raw[0, 6, 2] = 0.98  # class 2 (car), class 0 stays 0.0

    dets = decode_yolov8_person_output(raw, transform, confidence_threshold=0.45, iou_threshold=0.45)
    assert len(dets) == 1
    assert dets[0].confidence == pytest.approx(0.91)
    assert dets[0].bbox_px == (540, 160, 200, 400)
    assert dets[0].ground_point[0] == pytest.approx(0.5, abs=1e-3)
    assert dets[0].ground_point[1] == pytest.approx(560 / 720, abs=1e-3)


def test_edge_config_toml_and_env_override(tmp_path: Path) -> None:
    cfg_file = tmp_path / "edge.toml"
    node_id = uuid4()
    key_hex = os.urandom(32).hex()
    cfg_file.write_text(
        f'node_id = "{node_id}"\n'
        f"key_id = 1\n"
        f'encryption_key_hex = "{key_hex}"\n'
        f'gateway_ws_url = "ws://127.0.0.1:8000/ws/edge"\n'
        f'camera_source = 0\n'
        f'model_path = "{(tmp_path / "yolov8n.onnx").as_posix()}"\n'
        f'db_path = "{(tmp_path / "outbox.db").as_posix()}"\n'
        f"persistence_frames = 3\n",
        encoding="utf-8",
    )
    loaded = load_edge_config(
        config_path=cfg_file,
        environ={"SENTRA_PERSISTENCE_FRAMES": "5", "SENTRA_CAMERA_SOURCE": "2"},
    )
    assert loaded.node_id == node_id
    assert loaded.persistence_frames == 5
    assert loaded.camera_source == 2
    assert len(loaded.encryption_key) == 32


def test_uplink_worker_drains_intrusion_and_applies_fence_sync(tmp_path: Path) -> None:
    async def _run_e2e_ws() -> None:
        node_id = uuid4()
        key_id = 1
        key = os.urandom(32)
        fence_id = uuid4()
        new_fence_id = uuid4()
        event_id = uuid4()

        outbox = TransactionalOutbox(
            db_path=tmp_path / "ws_outbox.db",
            node_id=node_id,
            key_id=key_id,
            encryption_key=key,
        )
        fence_store = AtomicFenceStore()

        frame = _make_synthetic_frame(120, 160, fill_value=55)
        ev = extract_dual_evidence(frame, (0.2, 0.2, 0.3, 0.5), jpeg_quality=80)
        outbox.enqueue_intrusion(
            event_id=event_id,
            fence_id=fence_id,
            fence_version=1,
            confidence=0.94,
            bbox=(0.2, 0.2, 0.3, 0.5),
            ground_point=(0.35, 0.7),
            persistence_frames=3,
            wide_bytes=ev.wide_bytes,
            roi_bytes=ev.roi_bytes,
        )

        received_events: list[UUID] = []
        received_fence_acks: list[FenceAckPayload] = []
        received_heartbeats: list[HeartbeatPayload] = []
        server_done = asyncio.Event()
        server_seq = 0

        def _resolve(nid: UUID, kid: int) -> bytes:
            assert nid == node_id and kid == key_id
            return key

        async def _core_handler(ws) -> None:
            nonlocal server_seq
            # Push FENCE_SYNC immediately on connect
            server_seq += 1
            sync_frame = seal_control_frame(
                msg_type=MessageType.FENCE_SYNC,
                node_id=node_id,
                key_id=key_id,
                session_epoch=10,
                seq_counter=server_seq,
                key=key,
                payload=FenceSyncPayload(
                    fence_id=new_fence_id,
                    version=7,
                    name="South Gate",
                    vertices=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
                    is_active=True,
                ),
            )
            await ws.send(sync_frame)

            async for raw in ws:
                decrypted = open_frame(bytes(raw), _resolve)
                payload = decrypted.payload
                if isinstance(payload, DecryptedIntrusionEvent):
                    received_events.append(payload.metadata.event_id)
                    server_seq += 1
                    ack_frame = seal_control_frame(
                        msg_type=MessageType.EVENT_ACK,
                        node_id=node_id,
                        key_id=key_id,
                        session_epoch=10,
                        seq_counter=server_seq,
                        key=key,
                        payload=EventAckPayload(
                            event_id=payload.metadata.event_id,
                            seq_counter=decrypted.header.seq_counter,
                            status="ACCEPTED",
                            received_at_ns=time.time_ns(),
                        ),
                    )
                    await ws.send(ack_frame)
                elif isinstance(payload, FenceAckPayload):
                    received_fence_acks.append(payload)
                elif isinstance(payload, HeartbeatPayload):
                    received_heartbeats.append(payload)

                if received_events and received_fence_acks and received_heartbeats:
                    server_done.set()

        async with websockets.serve(_core_handler, "127.0.0.1", 0, compression=None) as server:
            port = server.sockets[0].getsockname()[1]
            worker = UplinkWorker(
                gateway_ws_url=f"ws://127.0.0.1:{port}",
                node_id=node_id,
                key_id=key_id,
                encryption_key=key,
                outbox=outbox,
                fence_store=fence_store,
                heartbeat_interval_sec=1.0,
                drain_poll_sec=0.05,
            )
            stop_event = asyncio.Event()
            worker_task = asyncio.create_task(worker.run(stop_event=stop_event))
            try:
                await asyncio.wait_for(server_done.wait(), timeout=5.0)
                # Give client a brief beat to process the EVENT_ACK
                for _ in range(40):
                    stats = outbox.get_stats()
                    if stats.pending_count == 0 and stats.in_flight_count == 0:
                        break
                    await asyncio.sleep(0.05)
            finally:
                stop_event.set()
                await asyncio.wait_for(worker_task, timeout=3.0)

        assert received_events == [event_id]
        assert len(received_fence_acks) == 1 and received_fence_acks[0].applied is True
        assert fence_store.active_version() == 7
        assert len(outbox.load_cached_fences()) == 1
        assert outbox.get_stats().pending_count == 0
        assert outbox.get_stats().in_flight_count == 0
        outbox.checkpoint_and_close()

    asyncio.run(_run_e2e_ws())
