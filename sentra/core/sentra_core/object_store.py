"""Private MinIO / S3v4 object store wrapper for encrypted dual-crop evidence."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from minio import Minio
from minio.deleteobjects import DeleteObject
from sentra_protocol.models import ImageFormat

logger = logging.getLogger(__name__)


def build_evidence_keys(
    *,
    node_id: UUID,
    detected_at: datetime,
    event_id: UUID,
    image_format: ImageFormat = "jpeg",
) -> tuple[str, str]:
    """Deterministic private S3 object keys: nodes/{node_id}/{YYYY}/{MM}/{DD}/{event_id}_{wide|roi}.{ext}."""
    utc_dt = detected_at.astimezone(timezone.utc)
    ext = "webp" if image_format == "webp" else "jpg"
    prefix = f"nodes/{node_id}/{utc_dt:%Y/%m/%d}/{event_id}"
    return f"{prefix}_wide.{ext}", f"{prefix}_roi.{ext}"


def _content_type(image_format: ImageFormat) -> str:
    return "image/webp" if image_format == "webp" else "image/jpeg"


class ObjectStore(Protocol):
    """Abstract async object-vault contract for evidence upload, presigning, and purge."""

    async def ensure_bucket(self) -> None: ...

    async def put_evidence(
        self,
        *,
        object_key: str,
        data: bytes,
        image_format: ImageFormat = "jpeg",
    ) -> None: ...

    async def generate_presigned_url(
        self,
        object_key: str,
        *,
        expires_in_sec: int = 300,
    ) -> str: ...

    async def delete_objects(self, object_keys: Sequence[str]) -> list[str]: ...


class MinioObjectStore:
    """Production private MinIO / S3v4 evidence vault backed by thread-offloaded Minio SDK."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = "sentra-evidence",
        secure: bool = False,
        presigned_ttl_sec: int = 300,
    ) -> None:
        self._bucket = bucket
        self._presigned_ttl_sec = presigned_ttl_sec
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def _ensure_bucket_sync(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Created private MinIO bucket: %s", self._bucket)

        # Enforce explicit empty/private bucket policy so objects are never public
        private_policy = {
            "Version": "2012-10-17",
            "Statement": [],
        }
        try:
            self._client.set_bucket_policy(self._bucket, json.dumps(private_policy))
        except Exception as exc:
            logger.warning("Unable to reset bucket policy on %s: %s", self._bucket, exc)

    async def ensure_bucket(self) -> None:
        """Ensure private evidence bucket exists on startup."""
        await asyncio.to_thread(self._ensure_bucket_sync)

    def _put_sync(self, object_key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    async def put_evidence(
        self,
        *,
        object_key: str,
        data: bytes,
        image_format: ImageFormat = "jpeg",
    ) -> None:
        """Upload raw evidence crop bytes to private MinIO vault."""
        await asyncio.to_thread(self._put_sync, object_key, data, _content_type(image_format))

    def _presign_sync(self, object_key: str, expires_in_sec: int) -> str:
        return self._client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=object_key,
            expires=timedelta(seconds=expires_in_sec),
        )

    async def generate_presigned_url(
        self,
        object_key: str,
        *,
        expires_in_sec: int | None = None,
    ) -> str:
        """Generate a short-lived S3v4 presigned GET URL without exposing bucket credentials."""
        ttl = self._presigned_ttl_sec if expires_in_sec is None else expires_in_sec
        return await asyncio.to_thread(self._presign_sync, object_key, ttl)

    def _delete_sync(self, object_keys: Sequence[str]) -> list[str]:
        if not object_keys:
            return []
        targets = [DeleteObject(key) for key in object_keys]
        errors = list(self._client.remove_objects(self._bucket, targets))
        failed = {err.name for err in errors if err.name}
        if failed:
            logger.error("Failed deleting %d object(s) from MinIO: %s", len(failed), failed)
        return [key for key in object_keys if key not in failed]

    async def delete_objects(self, object_keys: Sequence[str]) -> list[str]:
        """Batch-delete expired evidence objects and return keys successfully deleted."""
        return await asyncio.to_thread(self._delete_sync, object_keys)
