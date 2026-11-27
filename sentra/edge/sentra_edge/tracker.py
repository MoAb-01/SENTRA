"""Spatial-proximity multi-target N>=3 temporal persistence filter & peak-frame buffer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from sentra_protocol.models import NormalizedBBox, NormalizedPoint

from .detector import Detection


@dataclass(frozen=True, slots=True)
class ConfirmedIntrusion:
    """Emitted once a tracked target persists inside a fence for N frames."""

    fence_id: UUID
    fence_version: int
    track_id: int
    confidence: float
    bbox_norm: NormalizedBBox
    ground_point: NormalizedPoint
    persistence_frames: int
    peak_frame_bgr: NDArray[np.uint8]
    detected_at_ns: int


@dataclass(slots=True)
class _ActiveTrack:
    track_id: int
    fence_id: UUID
    last_bbox: NormalizedBBox
    last_ground_point: NormalizedPoint
    consecutive_hits: int
    missed_frames: int
    peak_confidence: float
    peak_bbox: NormalizedBBox
    peak_ground_point: NormalizedPoint
    peak_frame_bgr: NDArray[np.uint8]
    peak_timestamp_ns: int
    cooldown_until_ns: int = 0


def _bbox_iou(a: NormalizedBBox, b: NormalizedBBox) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0.0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0.0 else 0.0


def _centroid_distance(a: NormalizedPoint, b: NormalizedPoint) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class PersistenceFilter:
    """Multi-target per-fence temporal persistence filter with peak-frame retention.

    Suppresses transient <N-frame false positives, buffers the highest-confidence
    frame observed during the N-frame window, and enforces a per-track cooldown
    so a lingering person does not flood the outbox.
    """

    def __init__(
        self,
        *,
        persistence_frames: int = 3,
        max_miss_frames: int = 0,
        cooldown_sec: float = 10.0,
        match_iou_threshold: float = 0.20,
        max_centroid_distance: float = 0.15,
    ) -> None:
        if persistence_frames < 1:
            raise ValueError("persistence_frames must be >= 1")
        if max_miss_frames < 0:
            raise ValueError("max_miss_frames must be >= 0")
        if cooldown_sec < 0.0:
            raise ValueError("cooldown_sec must be >= 0.0")

        self._persistence_frames = persistence_frames
        self._max_miss_frames = max_miss_frames
        self._cooldown_ns = int(cooldown_sec * 1_000_000_000)
        self._match_iou_threshold = match_iou_threshold
        self._max_centroid_distance = max_centroid_distance

        self._next_track_id: int = 1
        self._tracks_by_fence: dict[UUID, dict[int, _ActiveTrack]] = {}

    def update(
        self,
        *,
        fence_id: UUID,
        fence_version: int,
        detections_inside: list[Detection],
        frame_bgr: NDArray[np.uint8],
        timestamp_ns: int,
    ) -> list[ConfirmedIntrusion]:
        """Advance track state for a single fence and return newly confirmed intrusions."""
        fence_tracks = self._tracks_by_fence.setdefault(fence_id, {})
        matched_tracks, unmatched_det_indices = self._match_detections(
            fence_tracks, detections_inside
        )

        confirmed: list[ConfirmedIntrusion] = []

        # 1. Update matched tracks
        for track_id, det_idx in matched_tracks:
            det = detections_inside[det_idx]
            track = fence_tracks[track_id]
            track.last_bbox = det.bbox_norm
            track.last_ground_point = det.ground_point
            track.missed_frames = 0

            # Suppress alert re-arming while target remains inside cooldown window
            if timestamp_ns < track.cooldown_until_ns:
                continue

            track.consecutive_hits += 1
            if track.consecutive_hits == 1 or det.confidence > track.peak_confidence:
                track.peak_confidence = det.confidence
                track.peak_bbox = det.bbox_norm
                track.peak_ground_point = det.ground_point
                track.peak_frame_bgr = frame_bgr.copy()
                track.peak_timestamp_ns = timestamp_ns

            if track.consecutive_hits == self._persistence_frames:
                confirmed.append(
                    ConfirmedIntrusion(
                        fence_id=fence_id,
                        fence_version=fence_version,
                        track_id=track.track_id,
                        confidence=track.peak_confidence,
                        bbox_norm=track.peak_bbox,
                        ground_point=track.peak_ground_point,
                        persistence_frames=self._persistence_frames,
                        peak_frame_bgr=track.peak_frame_bgr,
                        detected_at_ns=track.peak_timestamp_ns,
                    )
                )
                track.cooldown_until_ns = timestamp_ns + self._cooldown_ns
                track.consecutive_hits = 0
                track.peak_confidence = -1.0

        # 2. Age unmatched tracks and prune beyond max_miss_frames
        matched_ids = {tid for tid, _ in matched_tracks}
        stale_ids: list[int] = []
        for track_id, track in fence_tracks.items():
            if track_id not in matched_ids:
                track.missed_frames += 1
                if track.missed_frames > self._max_miss_frames:
                    stale_ids.append(track_id)
        for track_id in stale_ids:
            del fence_tracks[track_id]

        # 3. Create new tracks for unmatched detections
        for det_idx in unmatched_det_indices:
            det = detections_inside[det_idx]
            track_id = self._next_track_id
            self._next_track_id += 1
            new_track = _ActiveTrack(
                track_id=track_id,
                fence_id=fence_id,
                last_bbox=det.bbox_norm,
                last_ground_point=det.ground_point,
                consecutive_hits=1,
                missed_frames=0,
                peak_confidence=det.confidence,
                peak_bbox=det.bbox_norm,
                peak_ground_point=det.ground_point,
                peak_frame_bgr=frame_bgr.copy(),
                peak_timestamp_ns=timestamp_ns,
            )
            fence_tracks[track_id] = new_track

            if self._persistence_frames == 1:
                confirmed.append(
                    ConfirmedIntrusion(
                        fence_id=fence_id,
                        fence_version=fence_version,
                        track_id=new_track.track_id,
                        confidence=new_track.peak_confidence,
                        bbox_norm=new_track.peak_bbox,
                        ground_point=new_track.peak_ground_point,
                        persistence_frames=1,
                        peak_frame_bgr=new_track.peak_frame_bgr,
                        detected_at_ns=new_track.peak_timestamp_ns,
                    )
                )
                new_track.cooldown_until_ns = timestamp_ns + self._cooldown_ns
                new_track.consecutive_hits = 0
                new_track.peak_confidence = -1.0

        return confirmed

    def _match_detections(
        self,
        fence_tracks: dict[int, _ActiveTrack],
        detections: list[Detection],
    ) -> tuple[list[tuple[int, int]], list[int]]:
        """Greedy association prioritizing highest IoU, falling back to ground-point proximity."""
        if not fence_tracks or not detections:
            return [], list(range(len(detections)))

        candidates: list[tuple[float, int, int]] = []
        for track_id, track in fence_tracks.items():
            for det_idx, det in enumerate(detections):
                iou = _bbox_iou(track.last_bbox, det.bbox_norm)
                dist = _centroid_distance(track.last_ground_point, det.ground_point)
                if iou >= self._match_iou_threshold:
                    score = 1.0 + iou
                    candidates.append((score, track_id, det_idx))
                elif dist <= self._max_centroid_distance:
                    score = max(0.0, 1.0 - dist / self._max_centroid_distance)
                    candidates.append((score, track_id, det_idx))

        candidates.sort(key=lambda item: item[0], reverse=True)
        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        matches: list[tuple[int, int]] = []

        for _score, track_id, det_idx in candidates:
            if track_id in used_tracks or det_idx in used_dets:
                continue
            used_tracks.add(track_id)
            used_dets.add(det_idx)
            matches.append((track_id, det_idx))

        unmatched = [i for i in range(len(detections)) if i not in used_dets]
        return matches, unmatched
