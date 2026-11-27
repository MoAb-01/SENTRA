"""Strict Pydantic v2 data contracts for SENTRA payloads and geofence geometry."""

from __future__ import annotations

import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import MAX_FENCE_VERTICES, MIN_FENCE_VERTICES, MIN_POLYGON_AREA

ImageFormat = Literal["jpeg", "webp"]
AckStatus = Literal["ACCEPTED", "DUPLICATE"]
UserRole = Literal["ADMIN", "OPERATOR", "AUDITOR"]
NodeStatus = Literal["ONLINE", "DEGRADED", "OFFLINE", "REVOKED"]
TriageStatus = Literal["NEW", "ACKNOWLEDGED", "FALSE_POSITIVE", "ESCALATED"]

NormalizedPoint = tuple[float, float]
NormalizedBBox = tuple[float, float, float, float]


def _validate_unit_coord(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{label} must be within [0.0, 1.0], got {value}")
    return float(value)


def _orientation(a: NormalizedPoint, b: NormalizedPoint, c: NormalizedPoint) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: NormalizedPoint, b: NormalizedPoint, p: NormalizedPoint, eps: float = 1e-12) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def _segments_intersect(
    p1: NormalizedPoint,
    q1: NormalizedPoint,
    p2: NormalizedPoint,
    q2: NormalizedPoint,
    eps: float = 1e-12,
) -> bool:
    o1 = _orientation(p1, q1, p2)
    o2 = _orientation(p1, q1, q2)
    o3 = _orientation(p2, q2, p1)
    o4 = _orientation(p2, q2, q1)

    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    ):
        return True

    if abs(o1) <= eps and _on_segment(p1, q1, p2, eps):
        return True
    if abs(o2) <= eps and _on_segment(p1, q1, q2, eps):
        return True
    if abs(o3) <= eps and _on_segment(p2, q2, p1, eps):
        return True
    if abs(o4) <= eps and _on_segment(p2, q2, q1, eps):
        return True

    return False


def validate_polygon_vertices(vertices: list[NormalizedPoint]) -> list[NormalizedPoint]:
    """Validate 3..12 normalized [0.0, 1.0] vertices forming a non-degenerate simple polygon."""
    count = len(vertices)
    if count < MIN_FENCE_VERTICES or count > MAX_FENCE_VERTICES:
        raise ValueError(
            f"Virtual fence polygon must have between {MIN_FENCE_VERTICES} and "
            f"{MAX_FENCE_VERTICES} vertices, got {count}"
        )

    validated: list[NormalizedPoint] = []
    for idx, pt in enumerate(vertices):
        x = _validate_unit_coord(pt[0], f"vertices[{idx}].x")
        y = _validate_unit_coord(pt[1], f"vertices[{idx}].y")
        validated.append((x, y))

    # Reject duplicate vertices
    for i in range(count):
        for j in range(i + 1, count):
            if math.isclose(validated[i][0], validated[j][0], abs_tol=1e-9) and math.isclose(
                validated[i][1], validated[j][1], abs_tol=1e-9
            ):
                raise ValueError(f"Duplicate polygon vertex detected at indices {i} and {j}")

    # Reject zero-area / collinear degenerate polygons using the Shoelace formula
    double_area = 0.0
    for i in range(count):
        x1, y1 = validated[i]
        x2, y2 = validated[(i + 1) % count]
        double_area += (x1 * y2) - (x2 * y1)
    area = 0.5 * abs(double_area)
    if area < MIN_POLYGON_AREA:
        raise ValueError(
            f"Degenerate polygon with area {area:.9f} < {MIN_POLYGON_AREA} (collinear or collapsed vertices)"
        )

    # Reject self-intersecting polygons (non-adjacent edges must not intersect)
    for i in range(count):
        a1 = validated[i]
        a2 = validated[(i + 1) % count]
        for j in range(i + 1, count):
            # Skip identical or adjacent edges (including wrap-around edge 0 and count-1)
            if j == i or j == (i + 1) % count or (i == 0 and j == count - 1):
                continue
            b1 = validated[j]
            b2 = validated[(j + 1) % count]
            if _segments_intersect(a1, a2, b1, b2):
                raise ValueError(f"Self-intersecting polygon between edges {i} and {j}")

    return validated


class VirtualFencePolygon(BaseModel):
    """Normalized virtual fence polygon contract (3..12 non-degenerate vertices)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vertices: list[NormalizedPoint]

    @field_validator("vertices")
    @classmethod
    def _check_vertices(cls, value: list[NormalizedPoint]) -> list[NormalizedPoint]:
        return validate_polygon_vertices(value)


class IntrusionEventMetadata(BaseModel):
    """Authenticated JSON metadata inside an encrypted INTRUSION_EVENT container."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    fence_id: UUID
    fence_version: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: NormalizedBBox
    ground_point: NormalizedPoint
    persistence_frames: int = Field(ge=1, le=32767)
    wide_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    roi_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_format: ImageFormat

    @field_validator("confidence")
    @classmethod
    def _check_confidence_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("confidence must be finite")
        return float(value)

    @field_validator("bbox")
    @classmethod
    def _check_bbox(cls, value: NormalizedBBox) -> NormalizedBBox:
        x = _validate_unit_coord(value[0], "bbox.x")
        y = _validate_unit_coord(value[1], "bbox.y")
        w = _validate_unit_coord(value[2], "bbox.w")
        h = _validate_unit_coord(value[3], "bbox.h")
        if w <= 0.0 or h <= 0.0:
            raise ValueError("bbox width and height must be strictly positive")
        if x + w > 1.0 + 1e-6 or y + h > 1.0 + 1e-6:
            raise ValueError("bbox extends outside normalized [0.0, 1.0] frame bounds")
        return (x, y, w, h)

    @field_validator("ground_point")
    @classmethod
    def _check_ground_point(cls, value: NormalizedPoint) -> NormalizedPoint:
        return (
            _validate_unit_coord(value[0], "ground_point.xb"),
            _validate_unit_coord(value[1], "ground_point.yb"),
        )


class EventAckPayload(BaseModel):
    """Core -> Edge acknowledgement for an ingested or deduplicated INTRUSION_EVENT."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    seq_counter: int = Field(ge=1)
    status: AckStatus
    received_at_ns: int = Field(ge=0)


class HeartbeatPayload(BaseModel):
    """Bidirectional node liveness and outbox telemetry payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    uptime_s: int = Field(ge=0)
    outbox_depth: int = Field(ge=0)
    outbox_bytes: int = Field(ge=0)
    active_fence_version: int = Field(ge=0)
    cpu_temp_c: float | None = Field(default=None)

    @field_validator("cpu_temp_c")
    @classmethod
    def _check_temp_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("cpu_temp_c must be finite when provided")
        return value


class FenceSyncPayload(VirtualFencePolygon):
    """Core -> Edge virtual fence push payload."""

    fence_id: UUID
    version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=128)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _check_name_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Fence name must not be blank")
        return stripped


class FenceAckPayload(BaseModel):
    """Edge -> Core confirmation after persisting and hot-reloading a virtual fence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fence_id: UUID
    version: int = Field(ge=1)
    applied: bool
    error: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _check_error_consistency(self) -> FenceAckPayload:
        if self.applied and self.error is not None:
            raise ValueError("error must be None when applied is True")
        if not self.applied and not self.error:
            raise ValueError("error must be populated when applied is False")
        return self
