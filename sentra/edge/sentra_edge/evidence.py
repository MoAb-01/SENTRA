"""Dual-perspective evidence extractor: wide context + clamped upper-body/face RoI."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray
from sentra_protocol.models import ImageFormat, NormalizedBBox

_ROI_TOP_FRACTION: float = 0.35
_MIN_ROI_DIM_PX: int = 8


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Encoded wide-scene and upper-body RoI evidence buffers."""

    wide_bytes: bytes
    roi_bytes: bytes
    wide_size: tuple[int, int]             # (width, height)
    roi_size: tuple[int, int]              # (width, height)
    roi_rect_px: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    image_format: ImageFormat


def _encode_image(image_bgr: NDArray[np.uint8], quality: int, image_format: ImageFormat) -> bytes:
    if image_format == "webp":
        ext = ".webp"
        params = [int(cv2.IMWRITE_WEBP_QUALITY), int(quality)]
    else:
        ext = ".jpg"
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]

    ok, encoded = cv2.imencode(ext, image_bgr, params)
    if not ok or encoded.size == 0:
        raise RuntimeError(f"Failed to encode {image_format} buffer of shape {image_bgr.shape}")
    return encoded.tobytes()


def _clamp_span(start: int, end: int, limit: int, min_len: int) -> tuple[int, int]:
    """Clamp [start, end) to [0, limit] while guaranteeing at least min(min_len, limit) pixels."""
    target_min = min(min_len, limit)
    s = max(0, min(start, limit - target_min))
    e = max(s + target_min, min(end, limit))
    if e - s < target_min:
        s = max(0, limit - target_min)
        e = limit
    return s, e


def extract_dual_evidence(
    frame_bgr: NDArray[np.uint8],
    bbox_xywh_norm: NormalizedBBox,
    jpeg_quality: int = 85,
    image_format: ImageFormat = "jpeg",
) -> EvidenceBundle:
    """Encode full-frame context and clamped upper-body RoI [y : y + 0.35h, x : x + w].

    Applies strict frame-boundary clamping and falls back to full bbox height (and
    a minimum 8x8 px window when frame dimensions permit) so degenerate edge boxes
    never fail or produce empty buffers.
    """
    if frame_bgr.ndim < 2 or frame_bgr.shape[0] == 0 or frame_bgr.shape[1] == 0:
        raise ValueError(f"Invalid empty frame_bgr with shape {frame_bgr.shape}")

    frame_h, frame_w = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
    nx, ny, nw, nh = bbox_xywh_norm

    x1_raw = int(round(nx * frame_w))
    y1_raw = int(round(ny * frame_h))
    w_px = int(round(nw * frame_w))
    h_px = int(round(nh * frame_h))

    x2_raw = x1_raw + max(1, w_px)
    roi_h_px = int(round(h_px * _ROI_TOP_FRACTION))
    y2_upper = y1_raw + roi_h_px
    y2_full = y1_raw + max(1, h_px)

    # Strict horizontal clamp
    x1, x2 = _clamp_span(x1_raw, x2_raw, frame_w, _MIN_ROI_DIM_PX)

    # Strict vertical clamp for [y : y + 0.35h]; fall back to full bbox height if < 8px
    y1_clamped = max(0, min(y1_raw, frame_h))
    y2_clamped = max(0, min(y2_upper, frame_h))
    if (y2_clamped - y1_clamped) < _MIN_ROI_DIM_PX:
        y1, y2 = _clamp_span(y1_raw, y2_full, frame_h, _MIN_ROI_DIM_PX)
    else:
        y1, y2 = y1_clamped, y2_clamped

    roi_crop = frame_bgr[y1:y2, x1:x2]
    wide_bytes = _encode_image(frame_bgr, jpeg_quality, image_format)
    roi_bytes = _encode_image(roi_crop, jpeg_quality, image_format)

    return EvidenceBundle(
        wide_bytes=wide_bytes,
        roi_bytes=roi_bytes,
        wide_size=(frame_w, frame_h),
        roi_size=(int(roi_crop.shape[1]), int(roi_crop.shape[0])),
        roi_rect_px=(x1, y1, x2, y2),
        image_format=image_format,
    )
