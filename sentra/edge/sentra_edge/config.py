"""Typed Pydantic v2 configuration loader (TOML file + SENTRA_* environment overrides)."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sentra_protocol.constants import AES_256_KEY_SIZE, UINT32_MAX
from sentra_protocol.models import ImageFormat

ENV_PREFIX = "SENTRA_"
DEFAULT_MAX_OUTBOX_BYTES = 536_870_912  # 512 MiB

_ENV_FIELD_NAMES: tuple[str, ...] = (
    "node_id",
    "key_id",
    "encryption_key_hex",
    "gateway_ws_url",
    "camera_source",
    "model_path",
    "confidence_threshold",
    "iou_threshold",
    "persistence_frames",
    "max_miss_frames",
    "cooldown_sec",
    "jpeg_quality",
    "image_format",
    "db_path",
    "max_outbox_bytes",
    "heartbeat_interval_sec",
)


def _coerce_camera_source(value: Any) -> int | str:
    if isinstance(value, bool):
        raise ValueError("camera_source cannot be a boolean")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("USB camera_source index must be >= 0")
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("camera_source must not be empty")
        if stripped.isdigit():
            return int(stripped)
        return stripped
    raise ValueError(f"Unsupported camera_source type: {type(value).__name__}")


class EdgeConfig(BaseModel):
    """Production runtime settings for a SENTRA edge node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: UUID
    key_id: int = Field(ge=0, le=UINT32_MAX)
    encryption_key_hex: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    gateway_ws_url: str = Field(min_length=6)
    camera_source: int | str
    model_path: Path

    confidence_threshold: float = Field(default=0.45, ge=0.01, le=0.99)
    iou_threshold: float = Field(default=0.45, ge=0.05, le=0.95)
    persistence_frames: int = Field(default=3, ge=1, le=300)
    max_miss_frames: int = Field(default=0, ge=0, le=10)
    cooldown_sec: float = Field(default=10.0, ge=0.0, le=3600.0)

    jpeg_quality: int = Field(default=85, ge=10, le=100)
    image_format: ImageFormat = "jpeg"

    db_path: Path
    max_outbox_bytes: int = Field(default=DEFAULT_MAX_OUTBOX_BYTES, ge=1024)
    heartbeat_interval_sec: float = Field(default=15.0, ge=1.0, le=300.0)

    @field_validator("gateway_ws_url")
    @classmethod
    def _validate_ws_url(cls, value: str) -> str:
        stripped = value.strip()
        if not (stripped.startswith("ws://") or stripped.startswith("wss://")):
            raise ValueError("gateway_ws_url must start with 'ws://' or 'wss://'")
        return stripped

    @field_validator("camera_source", mode="before")
    @classmethod
    def _validate_camera_source(cls, value: Any) -> int | str:
        return _coerce_camera_source(value)

    @property
    def encryption_key(self) -> bytes:
        """Return the validated 32-byte AES-256 symmetric key."""
        key_bytes = bytes.fromhex(self.encryption_key_hex)
        if len(key_bytes) != AES_256_KEY_SIZE:
            raise ValueError(f"Encryption key must decode to {AES_256_KEY_SIZE} bytes")
        return key_bytes


def load_edge_config(
    config_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> EdgeConfig:
    """Load configuration from TOML file (SENTRA_CONFIG) overridden by SENTRA_* env vars."""
    env = os.environ if environ is None else environ
    merged: dict[str, Any] = {}

    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path)
    elif env_cfg := env.get("SENTRA_CONFIG"):
        resolved_path = Path(env_cfg)

    if resolved_path is not None:
        if not resolved_path.is_file():
            raise FileNotFoundError(f"SENTRA config file not found: {resolved_path}")
        with resolved_path.open("rb") as fh:
            toml_data = tomllib.load(fh)
        if not isinstance(toml_data, dict):
            raise ValueError("Top-level TOML configuration must be a table")
        merged.update(toml_data)

    for field_name in _ENV_FIELD_NAMES:
        env_key = f"{ENV_PREFIX}{field_name.upper()}"
        if env_key in env and env[env_key] != "":
            merged[field_name] = env[env_key]

    return EdgeConfig.model_validate(merged)
