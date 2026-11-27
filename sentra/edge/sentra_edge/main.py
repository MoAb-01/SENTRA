"""SENTRA Edge service orchestrator, latency telemetry, and graceful shutdown."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import threading
import time
from collections import deque
from uuid import uuid4

import numpy as np

from .capture import FrameGrabber
from .config import EdgeConfig, load_edge_config
from .detector import Detection, YoloOnnxDetector
from .evidence import extract_dual_evidence
from .geofence import AtomicFenceStore, points_in_polygon_batch
from .outbox import TransactionalOutbox
from .tracker import PersistenceFilter
from .uplink import UplinkWorker

logger = logging.getLogger("sentra_edge")

_TELEMETRY_WINDOW: int = 600
_HEALTH_LOG_INTERVAL_SEC: float = 60.0


class LatencyMetrics:
    """Rolling P50 / P95 / P99 stage latency collector."""

    def __init__(self, window_size: int = _TELEMETRY_WINDOW) -> None:
        self._inference_ms: deque[float] = deque(maxlen=window_size)
        self._pip_ms: deque[float] = deque(maxlen=window_size)
        self._total_ms: deque[float] = deque(maxlen=window_size)

    def record(self, *, inference_ms: float, pip_ms: float, total_ms: float) -> None:
        self._inference_ms.append(inference_ms)
        self._pip_ms.append(pip_ms)
        self._total_ms.append(total_ms)

    @staticmethod
    def _percentiles(samples: deque[float]) -> dict[str, float]:
        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        arr = np.asarray(samples, dtype=np.float64)
        p50, p95, p99 = np.percentile(arr, [50, 95, 99])
        return {
            "p50": round(float(p50), 3),
            "p95": round(float(p95), 3),
            "p99": round(float(p99), 3),
        }

    def snapshot(self) -> dict[str, object]:
        return {
            "samples": len(self._total_ms),
            "inference_ms": self._percentiles(self._inference_ms),
            "pip_ms": self._percentiles(self._pip_ms),
            "total_loop_ms": self._percentiles(self._total_ms),
        }


class EdgeService:
    """Orchestrates capture, inference, geofencing, tracking, outbox, and uplink."""

    def __init__(self, config: EdgeConfig) -> None:
        self._config = config
        self._stop_event = threading.Event()
        self._metrics = LatencyMetrics()

        self._outbox = TransactionalOutbox(
            db_path=config.db_path,
            node_id=config.node_id,
            key_id=config.key_id,
            encryption_key=config.encryption_key,
            max_outbox_bytes=config.max_outbox_bytes,
        )

        # Offline cold-start: immediately load cached fences from SQLite
        cached_fences = self._outbox.load_cached_fences()
        self._fence_store = AtomicFenceStore(initial_fences=cached_fences)
        logger.info("Loaded %d cached active fence(s) from SQLite", len(cached_fences))

        self._detector = YoloOnnxDetector(
            model_path=config.model_path,
            confidence_threshold=config.confidence_threshold,
            iou_threshold=config.iou_threshold,
        )
        self._tracker = PersistenceFilter(
            persistence_frames=config.persistence_frames,
            max_miss_frames=config.max_miss_frames,
            cooldown_sec=config.cooldown_sec,
        )
        self._grabber = FrameGrabber(source=config.camera_source)
        self._uplink = UplinkWorker(
            gateway_ws_url=config.gateway_ws_url,
            node_id=config.node_id,
            key_id=config.key_id,
            encryption_key=config.encryption_key,
            outbox=self._outbox,
            fence_store=self._fence_store,
            heartbeat_interval_sec=config.heartbeat_interval_sec,
        )

        self._uplink_loop: asyncio.AbstractEventLoop | None = None
        self._uplink_stop: asyncio.Event | None = None
        self._uplink_thread: threading.Thread | None = None

    def _run_uplink_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stop_evt = asyncio.Event()
        self._uplink_loop = loop
        self._uplink_stop = stop_evt
        try:
            loop.run_until_complete(self._uplink.run(stop_event=stop_evt))
        finally:
            loop.close()

    def request_shutdown(self) -> None:
        """Signal inference loop and background threads to exit cleanly."""
        self._stop_event.set()
        if self._uplink_loop is not None and self._uplink_stop is not None:
            self._uplink_loop.call_soon_threadsafe(self._uplink_stop.set)

    def run_forever(self) -> None:
        """Start all subsystems and process frames until shutdown signal."""
        self._grabber.start()
        self._uplink_thread = threading.Thread(
            target=self._run_uplink_thread,
            name="sentra-uplink-asyncio",
            daemon=True,
        )
        self._uplink_thread.start()

        last_health_log = time.monotonic()
        try:
            while not self._stop_event.is_set():
                captured = self._grabber.get_latest(timeout_sec=0.5)
                if captured is None:
                    continue

                loop_t0 = time.perf_counter()
                inf_t0 = time.perf_counter()
                detections = self._detector.detect_persons(captured.frame_bgr)
                inf_ms = (time.perf_counter() - inf_t0) * 1000.0

                pip_t0 = time.perf_counter()
                self._evaluate_fences_and_enqueue(
                    frame_bgr=captured.frame_bgr,
                    detections=detections,
                    wall_time_ns=captured.wall_time_ns,
                )
                pip_ms = (time.perf_counter() - pip_t0) * 1000.0
                total_ms = (time.perf_counter() - loop_t0) * 1000.0

                self._metrics.record(inference_ms=inf_ms, pip_ms=pip_ms, total_ms=total_ms)

                now_mono = time.monotonic()
                if now_mono - last_health_log >= _HEALTH_LOG_INTERVAL_SEC:
                    self._log_health_summary()
                    last_health_log = now_mono
        finally:
            self._shutdown_cleanup()

    def _evaluate_fences_and_enqueue(
        self,
        *,
        frame_bgr: np.ndarray,
        detections: list[Detection],
        wall_time_ns: int,
    ) -> None:
        fences = self._fence_store.get_active_fences()
        if not fences:
            return

        points_xy = (
            np.asarray([d.ground_point for d in detections], dtype=np.float64)
            if detections
            else np.zeros((0, 2), dtype=np.float64)
        )

        for fence in fences:
            if detections:
                inside_mask = points_in_polygon_batch(points_xy, fence.vertices)
                inside_dets = [d for d, flag in zip(detections, inside_mask) if flag]
            else:
                inside_dets = []

            confirmed_list = self._tracker.update(
                fence_id=fence.fence_id,
                fence_version=fence.version,
                detections_inside=inside_dets,
                frame_bgr=frame_bgr,
                timestamp_ns=wall_time_ns,
            )

            for intrusion in confirmed_list:
                evidence = extract_dual_evidence(
                    intrusion.peak_frame_bgr,
                    intrusion.bbox_norm,
                    jpeg_quality=self._config.jpeg_quality,
                    image_format=self._config.image_format,
                )
                record = self._outbox.enqueue_intrusion(
                    event_id=uuid4(),
                    fence_id=intrusion.fence_id,
                    fence_version=intrusion.fence_version,
                    confidence=intrusion.confidence,
                    bbox=intrusion.bbox_norm,
                    ground_point=intrusion.ground_point,
                    persistence_frames=intrusion.persistence_frames,
                    wide_bytes=evidence.wide_bytes,
                    roi_bytes=evidence.roi_bytes,
                    image_format=evidence.image_format,
                    timestamp_ns=intrusion.detected_at_ns,
                )
                logger.info(
                    "Queued confirmed intrusion event_id=%s seq=%d conf=%.3f bytes=%d",
                    record.event_id,
                    record.seq_counter,
                    intrusion.confidence,
                    record.frame_size_bytes,
                )

    def _log_health_summary(self) -> None:
        stats = self._outbox.get_stats()
        payload = {
            "event": "edge_health_summary",
            "node_id": str(self._config.node_id),
            "dropped_frames": self._grabber.dropped_frames,
            "active_fences": len(self._fence_store.get_active_fences()),
            "outbox_pending": stats.pending_count,
            "outbox_in_flight": stats.in_flight_count,
            "outbox_bytes": stats.total_bytes,
            "latency": self._metrics.snapshot(),
        }
        logger.info("%s", json.dumps(payload, separators=(",", ":")))

    def _shutdown_cleanup(self) -> None:
        logger.info("Shutting down SENTRA Edge node cleanly...")
        self.request_shutdown()
        self._grabber.stop(timeout_sec=5.0)
        if self._uplink_thread is not None:
            self._uplink_thread.join(timeout=5.0)
        self._outbox.checkpoint_and_close()
        logger.info("SENTRA Edge node shutdown complete (SQLite WAL checkpointed).")


def run_cli() -> None:
    """CLI entry point registering SIGINT/SIGTERM handlers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    config = load_edge_config()
    service = EdgeService(config)

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %d; initiating graceful shutdown", signum)
        service.request_shutdown()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    service.run_forever()


if __name__ == "__main__":
    run_cli()
    sys.exit(0)
