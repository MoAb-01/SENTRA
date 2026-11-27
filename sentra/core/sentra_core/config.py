"""Typed Pydantic v2 settings loader for SENTRA Core (TOML + SENTRA_CORE_* env)."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sentra_protocol.constants import AES_256_KEY_SIZE

ENV_PREFIX = "SENTRA_CORE_"

_ENV_FIELD_NAMES: tuple[str, ...] = (
    "postgres_dsn",
    "minio_endpoint",
    "minio_access_key",
    "minio_secret_key",
    "minio_bucket",
    "minio_secure",
    "presigned_ttl_sec",
    "jwt_secret_hex",
    "access_token_expire_minutes",
    "refresh_token_expire_days",
    "refresh_inactivity_days",
    "cookie_secure",
    "node_master_key_hex",
    "evidence_retention_days",
    "retention_sweep_interval_sec",
    "cors_origins",
)


class CoreConfig(BaseModel):
    """Production runtime settings for the SENTRA Central Cryptographic Gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    postgres_dsn: str = Field(min_length=10)

    minio_endpoint: str = Field(min_length=3)
    minio_access_key: str = Field(min_length=1)
    minio_secret_key: str = Field(min_length=1)
    minio_bucket: str = Field(default="sentra-evidence", min_length=3, max_length=63)
    minio_secure: bool = False
    presigned_ttl_sec: int = Field(default=300, ge=30, le=3600)

    jwt_secret_hex: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    # Dual-Token Safeguards: short-lived access (15-60m) + rotating refresh (7-30d)
    access_token_expire_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_expire_days: int = Field(default=14, ge=7, le=30)
    refresh_inactivity_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = True

    node_master_key_hex: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    evidence_retention_days: int = Field(default=30, ge=1, le=3650)
    retention_sweep_interval_sec: int = Field(default=3600, ge=10, le=86400)

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("cors_origins must be a list of origins or comma-separated string")

    @property
    def jwt_secret(self) -> bytes:
        secret = bytes.fromhex(self.jwt_secret_hex)
        if len(secret) != AES_256_KEY_SIZE:
            raise ValueError("jwt_secret_hex must decode to 32 bytes")
        return secret

    @property
    def node_master_key(self) -> bytes:
        key = bytes.fromhex(self.node_master_key_hex)
        if len(key) != AES_256_KEY_SIZE:
            raise ValueError("node_master_key_hex must decode to 32 bytes")
        return key


def load_core_config(
    config_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> CoreConfig:
    """Load Core settings from SENTRA_CORE_CONFIG TOML overridden by SENTRA_CORE_* env."""
    env = os.environ if environ is None else environ
    merged: dict[str, Any] = {}

    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path)
    elif env_cfg := env.get("SENTRA_CORE_CONFIG"):
        resolved_path = Path(env_cfg)

    if resolved_path is not None:
        if not resolved_path.is_file():
            raise FileNotFoundError(f"SENTRA Core config file not found: {resolved_path}")
        with resolved_path.open("rb") as fh:
            toml_data = tomllib.load(fh)
        if not isinstance(toml_data, dict):
            raise ValueError("Top-level TOML configuration must be a table")
        merged.update(toml_data)

    for field_name in _ENV_FIELD_NAMES:
        env_key = f"{ENV_PREFIX}{field_name.upper()}"
        if env_key in env and env[env_key] != "":
            merged[field_name] = env[env_key]

    return CoreConfig.model_validate(merged)
