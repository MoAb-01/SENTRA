"""Quantized YOLOv8n ONNX Runtime detector with exact letterbox, decoding, and NMS."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray
from sentra_protocol.models import NormalizedBBox

logger = logging.getLogger(__name__)

COCO_PERSON_CLASS_ID: int = 0
YOLO_INPUT_SIZE: int = 640
LETTERBOX_PAD_VALUE: int = 114

PREFERRED_PROVIDERS: tuple[str, ...] = (
    "TensorrtExecutionProvider",
    "CUDAExecutionProvider",
    "OpenVINOExecutionProvider",
    "CPUExecutionProvider",
)


@dataclass(frozen=True, slots=True)
class Detection:
    """Single validated person detection in normalized and pixel coordinates."""

    bbox_norm: NormalizedBBox              # (x, y, w, h) in [0.0, 1.0]
    bbox_px: tuple[int, int, int, int]     # (x, y, w, h) in original frame pixels
    confidence: float
    class_id: int = COCO_PERSON_CLASS_ID

    @property
    def ground_point(self) -> tuple[float, float]:
        """Normalized ground-contact point (xb, yb) = (x + w/2, y + h)."""
        nx, ny, nw, nh = self.bbox_norm
        return (min(1.0, max(0.0, nx + nw * 0.5)), min(1.0, max(0.0, ny + nh)))


@dataclass(frozen=True, slots=True)
class LetterboxTransform:
    """Metadata needed to map 640x640 letterboxed boxes back to original pixels."""

    scale: float
    pad_x: float
    pad_y: float
    orig_w: int
    orig_h: int


def select_execution_providers() -> list[str]:
    """Intersect preferred hardware execution providers with available ORT providers."""
    available = set(ort.get_available_providers())
    selected = [p for p in PREFERRED_PROVIDERS if p in available]
    if not selected:
        selected = ["CPUExecutionProvider"]
    return selected


def letterbox_bgr(
    frame_bgr: NDArray[np.uint8],
    target_size: int = YOLO_INPUT_SIZE,
) -> tuple[NDArray[np.float32], LetterboxTransform]:
    """Exact YOLOv8 letterbox preprocessing: 640x640, pad 114, BGR->RGB, CHW, float32/255."""
    orig_h, orig_w = int(frame_bgr.shape[0]), int(frame_bgr.shape[1])
    if orig_h <= 0 or orig_w <= 0:
        raise ValueError(f"Invalid frame shape for letterbox: {frame_bgr.shape}")

    scale = min(target_size / orig_w, target_size / orig_h)
    new_w = int(round(orig_w * scale))
    new_h = int(round(orig_h * scale))

    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_w = target_size - new_w
    pad_h = target_size - new_h
    pad_left = pad_w // 2
    pad_top = pad_h // 2
    pad_right = pad_w - pad_left
    pad_bottom = pad_h - pad_top

    padded = cv2.copyMakeBorder(
        resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv2.BORDER_CONSTANT,
        value=(LETTERBOX_PAD_VALUE, LETTERBOX_PAD_VALUE, LETTERBOX_PAD_VALUE),
    )

    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    chw = np.transpose(rgb, (2, 0, 1))
    tensor = np.ascontiguousarray(chw, dtype=np.float32) * (1.0 / 255.0)
    tensor = np.expand_dims(tensor, axis=0)  # (1, 3, 640, 640)

    transform = LetterboxTransform(
        scale=scale,
        pad_x=float(pad_left),
        pad_y=float(pad_top),
        orig_w=orig_w,
        orig_h=orig_h,
    )
    return tensor, transform


def nms_xywh(
    boxes_xywh: NDArray[np.float32],
    scores: NDArray[np.float32],
    iou_threshold: float,
) -> list[int]:
    """Pure vectorized NumPy Non-Maximum Suppression on [x, y, w, h] pixel boxes."""
    if boxes_xywh.shape[0] == 0:
        return []

    x1 = boxes_xywh[:, 0]
    y1 = boxes_xywh[:, 1]
    x2 = x1 + boxes_xywh[:, 2]
    y2 = y1 + boxes_xywh[:, 3]
    areas = np.maximum(0.0, boxes_xywh[:, 2]) * np.maximum(0.0, boxes_xywh[:, 3])

    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break

        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])

        inter_w = np.maximum(0.0, xx2 - xx1)
        inter_h = np.maximum(0.0, yy2 - yy1)
        inter = inter_w * inter_h
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0.0, inter / union, 0.0)

        order = rest[iou <= iou_threshold]

    return keep


def decode_yolov8_person_output(
    raw_output: NDArray[np.floating],
    transform: LetterboxTransform,
    *,
    confidence_threshold: float,
    iou_threshold: float,
) -> list[Detection]:
    """Decode YOLOv8 [1, 84, 8400] tensor, strictly filtering COCO class 0 (person)."""
    arr = np.asarray(raw_output, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"Unexpected YOLOv8 output tensor shape: {raw_output.shape}")

    # Normalize layout to (num_anchors, 4 + num_classes); standard YOLOv8 is (84, 8400)
    if arr.shape[0] < arr.shape[1] and arr.shape[0] >= 5:
        preds = arr.T  # (8400, 84)
    else:
        preds = arr

    if preds.shape[1] < 5:
        raise ValueError(f"YOLOv8 prediction width too narrow: {preds.shape}")

    # Column 4 is COCO class 0 (person) confidence
    person_scores = preds[:, 4 + COCO_PERSON_CLASS_ID]
    mask = person_scores >= confidence_threshold
    if not np.any(mask):
        return []

    filtered = preds[mask]
    scores = person_scores[mask]

    # Convert center (cx, cy, w, h) in letterbox space -> top-left (x, y, w, h) in original pixels
    cx = filtered[:, 0]
    cy = filtered[:, 1]
    bw = filtered[:, 2]
    bh = filtered[:, 3]

    x1 = np.clip((cx - bw * 0.5 - transform.pad_x) / transform.scale, 0.0, float(transform.orig_w))
    y1 = np.clip((cy - bh * 0.5 - transform.pad_y) / transform.scale, 0.0, float(transform.orig_h))
    x2 = np.clip((cx + bw * 0.5 - transform.pad_x) / transform.scale, 0.0, float(transform.orig_w))
    y2 = np.clip((cy + bh * 0.5 - transform.pad_y) / transform.scale, 0.0, float(transform.orig_h))

    w_px = x2 - x1
    h_px = y2 - y1
    valid_dims = (w_px > 1.0) & (h_px > 1.0)
    if not np.any(valid_dims):
        return []

    boxes_xywh = np.stack((x1[valid_dims], y1[valid_dims], w_px[valid_dims], h_px[valid_dims]), axis=1)
    scores_valid = scores[valid_dims]

    keep_indices = nms_xywh(boxes_xywh, scores_valid, iou_threshold)
    inv_w = 1.0 / float(transform.orig_w)
    inv_h = 1.0 / float(transform.orig_h)

    detections: list[Detection] = []
    for idx in keep_indices:
        bx, by, bw_i, bh_i = boxes_xywh[idx]
        nx = float(np.clip(bx * inv_w, 0.0, 1.0))
        ny = float(np.clip(by * inv_h, 0.0, 1.0))
        nw = float(np.clip(bw_i * inv_w, 1e-6, 1.0 - nx))
        nh = float(np.clip(bh_i * inv_h, 1e-6, 1.0 - ny))
        detections.append(
            Detection(
                bbox_norm=(nx, ny, nw, nh),
                bbox_px=(int(round(bx)), int(round(by)), int(round(bw_i)), int(round(bh_i))),
                confidence=float(np.clip(scores_valid[idx], 0.0, 1.0)),
                class_id=COCO_PERSON_CLASS_ID,
            )
        )
    return detections


class YoloOnnxDetector:
    """ONNX Runtime YOLOv8n detector loading quantized FP16/INT8 weights once at startup."""

    def __init__(
        self,
        model_path: Path,
        *,
        confidence_threshold: float = 0.45,
        iou_threshold: float = 0.45,
        input_size: int = YOLO_INPUT_SIZE,
    ) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"YOLOv8n ONNX model not found: {model_path}")

        self._confidence_threshold = confidence_threshold
        self._iou_threshold = iou_threshold
        self._input_size = input_size

        providers = select_execution_providers()
        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=sess_opts,
            providers=providers,
        )
        self._input_name: str = self._session.get_inputs()[0].name
        self._output_name: str = self._session.get_outputs()[0].name
        self._active_providers: list[str] = list(self._session.get_providers())
        logger.info("Loaded YOLOv8n ONNX (%s) with providers=%s", model_path, self._active_providers)

    @property
    def active_providers(self) -> list[str]:
        return list(self._active_providers)

    def detect_persons(self, frame_bgr: NDArray[np.uint8]) -> list[Detection]:
        """Run quantized YOLOv8n inference and return filtered person detections."""
        tensor, transform = letterbox_bgr(frame_bgr, target_size=self._input_size)
        raw_output = self._session.run([self._output_name], {self._input_name: tensor})[0]
        return decode_yolov8_person_output(
            raw_output,
            transform,
            confidence_threshold=self._confidence_threshold,
            iou_threshold=self._iou_threshold,
        )
