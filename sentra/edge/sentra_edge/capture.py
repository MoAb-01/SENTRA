"""Decoupled 1-frame latest-buffer video grabber with exponential-backoff reconnect."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

_MIN_RECONNECT_SEC: float = 0.5
_MAX_RECONNECT_SEC: float = 10.0


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """Single latest video frame with monotonic and UTC wall-clock timestamps."""

    frame_bgr: NDArray[np.uint8]
    monotonic_ns: int
    wall_time_ns: int
    frame_index: int


def _default_capture_factory(source: int | str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class FrameGrabber:
    """Background daemon grabber storing only the newest frame (1-frame latest buffer).

    Slow inference or temporary network stalls drop stale unread frames instead
    of allowing RTSP or V4L2 driver buffers to build latency.
    """

    def __init__(
        self,
        source: int | str,
        *,
        min_reconnect_sec: float = _MIN_RECONNECT_SEC,
        max_reconnect_sec: float = _MAX_RECONNECT_SEC,
        capture_factory: Callable[[int | str], cv2.VideoCapture] = _default_capture_factory,
    ) -> None:
        self._source = source
        self._min_reconnect_sec = min_reconnect_sec
        self._max_reconnect_sec = max_reconnect_sec
        self._capture_factory = capture_factory

        self._lock = threading.Lock()
        self._new_frame_cond = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._latest: CapturedFrame | None = None
        self._last_consumed_index: int = 0
        self._frame_counter: int = 0
        self._dropped_frames: int = 0

    @property
    def dropped_frames(self) -> int:
        with self._lock:
            return self._dropped_frames

    def start(self) -> None:
        """Start the background frame grabber daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="sentra-frame-grabber",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_sec: float = 5.0) -> None:
        """Signal the grabber thread to stop and wait for clean camera release."""
        self._stop_event.set()
        with self._new_frame_cond:
            self._new_frame_cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=timeout_sec)
            self._thread = None

    def get_latest(self, timeout_sec: float = 1.0) -> CapturedFrame | None:
        """Return the newest unread frame, waiting up to timeout_sec if none is ready."""
        deadline = time.monotonic() + timeout_sec
        with self._new_frame_cond:
            while not self._stop_event.is_set():
                if (
                    self._latest is not None
                    and self._latest.frame_index > self._last_consumed_index
                ):
                    frame = self._latest
                    self._last_consumed_index = frame.frame_index
                    return frame

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._new_frame_cond.wait(timeout=remaining)
        return None

    def _run_loop(self) -> None:
        backoff = self._min_reconnect_sec
        cap: cv2.VideoCapture | None = None

        try:
            while not self._stop_event.is_set():
                if cap is None or not cap.isOpened():
                    cap = self._open_source()
                    if cap is None:
                        logger.warning(
                            "Camera source unavailable (%r); retrying in %.2fs",
                            self._source,
                            backoff,
                        )
                        if self._stop_event.wait(backoff):
                            break
                        backoff = min(backoff * 2.0, self._max_reconnect_sec)
                        continue
                    backoff = self._min_reconnect_sec
                    logger.info("Connected to camera source: %r", self._source)

                ok, frame = cap.read()
                if not ok or frame is None or frame.size == 0:
                    logger.warning(
                        "Camera stream read failed (%r); reconnecting in %.2fs",
                        self._source,
                        backoff,
                    )
                    self._release_capture(cap)
                    cap = None
                    if self._stop_event.wait(backoff):
                        break
                    backoff = min(backoff * 2.0, self._max_reconnect_sec)
                    continue

                backoff = self._min_reconnect_sec
                mono_ns = time.monotonic_ns()
                wall_ns = time.time_ns()

                with self._new_frame_cond:
                    if (
                        self._latest is not None
                        and self._latest.frame_index > self._last_consumed_index
                    ):
                        self._dropped_frames += 1
                    self._frame_counter += 1
                    self._latest = CapturedFrame(
                        frame_bgr=frame,
                        monotonic_ns=mono_ns,
                        wall_time_ns=wall_ns,
                        frame_index=self._frame_counter,
                    )
                    self._new_frame_cond.notify_all()
        finally:
            self._release_capture(cap)

    def _open_source(self) -> cv2.VideoCapture | None:
        try:
            cap = self._capture_factory(self._source)
        except Exception:
            logger.exception("Exception opening camera source %r", self._source)
            return None

        if cap is None or not cap.isOpened():
            self._release_capture(cap)
            return None
        return cap

    @staticmethod
    def _release_capture(cap: cv2.VideoCapture | None) -> None:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                logger.exception("Error releasing cv2.VideoCapture handle")
