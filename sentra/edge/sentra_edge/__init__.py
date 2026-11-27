"""SENTRA Edge Node Engine."""

from .capture import CapturedFrame, FrameGrabber
from .config import EdgeConfig, load_edge_config
from .detector import Detection, YoloOnnxDetector, decode_yolov8_person_output, letterbox_bgr, nms_xywh
from .evidence import EvidenceBundle, extract_dual_evidence
from .geofence import AtomicFenceStore, FencePolygon, points_in_polygon_batch
from .outbox import OutboxRecord, OutboxStats, TransactionalOutbox
from .tracker import ConfirmedIntrusion, PersistenceFilter
from .uplink import UplinkWorker

__all__ = [
    "AtomicFenceStore",
    "CapturedFrame",
    "ConfirmedIntrusion",
    "Detection",
    "EdgeConfig",
    "EvidenceBundle",
    "FencePolygon",
    "FrameGrabber",
    "OutboxRecord",
    "OutboxStats",
    "PersistenceFilter",
    "TransactionalOutbox",
    "UplinkWorker",
    "YoloOnnxDetector",
    "decode_yolov8_person_output",
    "extract_dual_evidence",
    "letterbox_bgr",
    "load_edge_config",
    "nms_xywh",
    "points_in_polygon_batch",
]
