"""Vectorized NumPy Ray-Casting Point-in-Polygon engine and lock-free AtomicFenceStore."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from sentra_protocol.constants import MAX_FENCE_VERTICES, MIN_FENCE_VERTICES
from sentra_protocol.models import FenceSyncPayload, NormalizedPoint, VirtualFencePolygon

_HORIZONTAL_EPS: float = 1e-12


@dataclass(frozen=True, slots=True)
class FencePolygon:
    """Immutable, pre-converted NumPy polygon ready for hot-path Ray-Casting."""

    fence_id: UUID
    version: int
    name: str
    vertices: NDArray[np.float64]  # shape (V, 2), normalized [0.0, 1.0]
    is_active: bool = True

    @classmethod
    def from_sync_payload(cls, payload: FenceSyncPayload) -> FencePolygon:
        """Construct a validated FencePolygon from a Phase 1 FenceSyncPayload."""
        coords = np.asarray(payload.vertices, dtype=np.float64)
        return cls(
            fence_id=payload.fence_id,
            version=payload.version,
            name=payload.name,
            vertices=coords,
            is_active=payload.is_active,
        )

    @classmethod
    def from_vertices(
        cls,
        *,
        fence_id: UUID,
        version: int,
        name: str,
        vertices: Sequence[NormalizedPoint],
        is_active: bool = True,
    ) -> FencePolygon:
        """Validate vertices via Phase 1 VirtualFencePolygon and build a FencePolygon."""
        validated = VirtualFencePolygon(vertices=list(vertices))
        coords = np.asarray(validated.vertices, dtype=np.float64)
        return cls(
            fence_id=fence_id,
            version=version,
            name=name,
            vertices=coords,
            is_active=is_active,
        )


def points_in_polygon_batch(
    points_xy: NDArray[np.floating],
    polygon_xy: NDArray[np.floating],
) -> NDArray[np.bool_]:
    """Vectorized Jordan Curve Ray-Casting for M points against a V-vertex polygon.

    Args:
        points_xy: Array of shape (M, 2) containing ground-contact points (xb, yb).
        polygon_xy: Array of shape (V, 2) with 3 <= V <= 12 polygon vertices.

    Returns:
        Boolean array of shape (M,) where True indicates point is inside polygon.
    """
    pts = np.asarray(points_xy, dtype=np.float64)
    poly = np.asarray(polygon_xy, dtype=np.float64)

    if poly.ndim != 2 or poly.shape[1] != 2:
        raise ValueError(f"polygon_xy must have shape (V, 2), got {poly.shape}")
    v_count = poly.shape[0]
    if v_count < MIN_FENCE_VERTICES or v_count > MAX_FENCE_VERTICES:
        raise ValueError(
            f"Polygon must have between {MIN_FENCE_VERTICES} and {MAX_FENCE_VERTICES} vertices, got {v_count}"
        )

    if pts.size == 0:
        return np.zeros((0,), dtype=np.bool_)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"points_xy must have shape (M, 2), got {pts.shape}")

    px = pts[:, 0:1]  # (M, 1)
    py = pts[:, 1:2]  # (M, 1)

    x1 = poly[:, 0]             # (V,)
    y1 = poly[:, 1]             # (V,)
    x2 = np.roll(x1, -1)        # (V,)
    y2 = np.roll(y1, -1)        # (V,)

    # Strict half-open vertical interval check: eliminates double-counting vertices
    # and guarantees horizontal edges (y1 == y2) always evaluate to False.
    crosses_y = (y1 > py) != (y2 > py)

    dy = y2 - y1
    safe_dy = np.where(np.abs(dy) < _HORIZONTAL_EPS, _HORIZONTAL_EPS, dy)
    x_intersect = x1 + ((py - y1) * (x2 - x1)) / safe_dy

    hits = crosses_y & (px < x_intersect)
    return (np.count_nonzero(hits, axis=1) & 1).astype(np.bool_)


class AtomicFenceStore:
    """Lock-free hot-path store holding immutable active virtual fences.

    Swapping the backing tuple reference is atomic in Python, allowing the
    background uplink thread to hot-reload synced fences with zero contention
    on the real-time inference thread.
    """

    def __init__(self, initial_fences: Sequence[FencePolygon] = ()) -> None:
        self._fences: tuple[FencePolygon, ...] = tuple(
            f for f in initial_fences if f.is_active
        )

    def get_active_fences(self) -> tuple[FencePolygon, ...]:
        """Return the current immutable snapshot of active fences."""
        return self._fences

    def active_version(self) -> int:
        """Return the highest version among active fences (0 if none loaded)."""
        fences = self._fences
        if not fences:
            return 0
        return max(f.version for f in fences)

    def replace_all(self, fences: Sequence[FencePolygon]) -> None:
        """Atomically replace all active fences."""
        self._fences = tuple(f for f in fences if f.is_active)

    def upsert_fence(self, fence: FencePolygon) -> tuple[FencePolygon, ...]:
        """Atomically upsert or deactivate a single fence and return the new snapshot."""
        by_id: dict[UUID, FencePolygon] = {f.fence_id: f for f in self._fences}
        if fence.is_active:
            by_id[fence.fence_id] = fence
        else:
            by_id.pop(fence.fence_id, None)
        new_snapshot = tuple(by_id.values())
        self._fences = new_snapshot
        return new_snapshot
