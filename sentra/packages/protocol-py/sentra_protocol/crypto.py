"""AES-256-GCM sealing, opening, AAD binding, and SHA-256 chain-of-custody verification."""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from .constants import (
    AAD_SIZE,
    AES_256_KEY_SIZE,
    GCM_TAG_SIZE,
    MAX_PLAINTEXT_SIZE,
    MessageType,
)
from .errors import (
    AuthenticationError,
    IntegrityError,
    InvalidKeyError,
    OversizedFrameError,
    ReplayError,
)
from .framing import (
    FrameHeader,
    derive_nonce,
    pack_header,
    pack_intrusion_container,
    parse_nonce,
    unpack_frame,
    unpack_intrusion_container,
)
from .models import (
    EventAckPayload,
    FenceAckPayload,
    FenceSyncPayload,
    HeartbeatPayload,
    ImageFormat,
    IntrusionEventMetadata,
    NormalizedBBox,
    NormalizedPoint,
)

KeyResolver: TypeAlias = Callable[[UUID, int], bytes]


@dataclass(frozen=True, slots=True)
class DecryptedIntrusionEvent:
    """Verified, decrypted INTRUSION_EVENT metadata and binary image buffers."""

    metadata: IntrusionEventMetadata
    wide_bytes: bytes
    roi_bytes: bytes


DecryptedPayload: TypeAlias = (
    DecryptedIntrusionEvent
    | EventAckPayload
    | HeartbeatPayload
    | FenceSyncPayload
    | FenceAckPayload
)


@dataclass(frozen=True, slots=True)
class DecryptedFrame:
    """Authenticated and integrity-verified SENTRA v1 frame."""

    header: FrameHeader
    session_epoch: int
    payload: DecryptedPayload


def _validate_aes256_key(key: bytes) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or len(key) != AES_256_KEY_SIZE:
        actual = len(key) if isinstance(key, (bytes, bytearray)) else type(key).__name__
        raise InvalidKeyError(
            f"AES-256-GCM requires a {AES_256_KEY_SIZE}-byte key, got {actual}"
        )
    return bytes(key)


def _seal_raw(
    *,
    msg_type: MessageType,
    node_id: UUID,
    key_id: int,
    session_epoch: int,
    seq_counter: int,
    key: bytes,
    plaintext: bytes,
    timestamp_ns: int | None = None,
) -> bytes:
    validated_key = _validate_aes256_key(key)

    if len(plaintext) > MAX_PLAINTEXT_SIZE:
        raise OversizedFrameError(
            f"Plaintext size ({len(plaintext)}) exceeds MAX_PLAINTEXT_SIZE ({MAX_PLAINTEXT_SIZE})"
        )

    ts = time.time_ns() if timestamp_ns is None else timestamp_ns
    nonce = derive_nonce(session_epoch, seq_counter)
    payload_len = len(plaintext) + GCM_TAG_SIZE

    header_bytes = pack_header(
        msg_type=msg_type,
        node_id=node_id,
        key_id=key_id,
        seq_counter=seq_counter,
        timestamp_ns=ts,
        nonce=nonce,
        payload_len=payload_len,
    )

    aad = header_bytes[:AAD_SIZE]
    ciphertext_and_tag = AESGCM(validated_key).encrypt(nonce, plaintext, aad)
    return header_bytes + ciphertext_and_tag


def seal_intrusion_event(
    *,
    node_id: UUID,
    key_id: int,
    session_epoch: int,
    seq_counter: int,
    key: bytes,
    event_id: UUID,
    fence_id: UUID,
    fence_version: int,
    confidence: float,
    bbox: NormalizedBBox,
    ground_point: NormalizedPoint,
    persistence_frames: int,
    wide_bytes: bytes,
    roi_bytes: bytes,
    image_format: ImageFormat = "webp",
    timestamp_ns: int | None = None,
) -> bytes:
    """Compute SHA-256 digests, pack binary container, and seal an INTRUSION_EVENT frame."""
    if not wide_bytes:
        raise ValueError("wide_bytes must not be empty")
    if not roi_bytes:
        raise ValueError("roi_bytes must not be empty")

    wide_sha256 = hashlib.sha256(wide_bytes).hexdigest()
    roi_sha256 = hashlib.sha256(roi_bytes).hexdigest()

    metadata = IntrusionEventMetadata(
        event_id=event_id,
        fence_id=fence_id,
        fence_version=fence_version,
        confidence=confidence,
        bbox=bbox,
        ground_point=ground_point,
        persistence_frames=persistence_frames,
        wide_sha256=wide_sha256,
        roi_sha256=roi_sha256,
        image_format=image_format,
    )

    meta_json_bytes = metadata.model_dump_json().encode("utf-8")
    plaintext = pack_intrusion_container(meta_json_bytes, wide_bytes, roi_bytes)

    return _seal_raw(
        msg_type=MessageType.INTRUSION_EVENT,
        node_id=node_id,
        key_id=key_id,
        session_epoch=session_epoch,
        seq_counter=seq_counter,
        key=key,
        plaintext=plaintext,
        timestamp_ns=timestamp_ns,
    )


def seal_control_frame(
    *,
    msg_type: MessageType,
    node_id: UUID,
    key_id: int,
    session_epoch: int,
    seq_counter: int,
    key: bytes,
    payload: EventAckPayload | HeartbeatPayload | FenceSyncPayload | FenceAckPayload,
    timestamp_ns: int | None = None,
) -> bytes:
    """Seal an encrypted JSON control/sync frame (EVENT_ACK, HEARTBEAT, FENCE_SYNC, FENCE_ACK)."""
    expected_map: dict[MessageType, type] = {
        MessageType.EVENT_ACK: EventAckPayload,
        MessageType.HEARTBEAT: HeartbeatPayload,
        MessageType.FENCE_SYNC: FenceSyncPayload,
        MessageType.FENCE_ACK: FenceAckPayload,
    }
    expected_cls = expected_map.get(msg_type)
    if expected_cls is None:
        raise ValueError(f"Use seal_intrusion_event for message type {msg_type.name}")
    if not isinstance(payload, expected_cls):
        raise TypeError(
            f"Expected {expected_cls.__name__} for {msg_type.name}, got {type(payload).__name__}"
        )

    plaintext = payload.model_dump_json().encode("utf-8")
    return _seal_raw(
        msg_type=msg_type,
        node_id=node_id,
        key_id=key_id,
        session_epoch=session_epoch,
        seq_counter=seq_counter,
        key=key,
        plaintext=plaintext,
        timestamp_ns=timestamp_ns,
    )


def open_frame(raw_frame: bytes, key_resolver: KeyResolver) -> DecryptedFrame:
    """Parse, authenticate (AES-256-GCM + 42-byte AAD), and verify a SENTRA v1 wire frame."""
    parsed = unpack_frame(raw_frame)
    header = parsed.header

    try:
        resolved_key = key_resolver(header.node_id, header.key_id)
    except InvalidKeyError:
        raise
    except Exception as exc:
        raise InvalidKeyError(
            f"Failed to resolve key for node={header.node_id} key_id={header.key_id}"
        ) from exc

    key = _validate_aes256_key(resolved_key)

    try:
        plaintext = AESGCM(key).decrypt(header.nonce, parsed.ciphertext_and_tag, parsed.aad)
    except InvalidTag as exc:
        raise AuthenticationError(
            f"AES-256-GCM authentication failed for node={header.node_id} seq={header.seq_counter}"
        ) from exc

    # Defense-in-depth: verify deterministic nonce embeds header.seq_counter
    session_epoch, nonce_seq = parse_nonce(header.nonce)
    if nonce_seq != header.seq_counter:
        raise IntegrityError(
            f"Nonce sequence ({nonce_seq}) does not match header seq_counter ({header.seq_counter})"
        )

    if header.msg_type is MessageType.INTRUSION_EVENT:
        meta_json, wide_bytes, roi_bytes = unpack_intrusion_container(plaintext)
        try:
            metadata = IntrusionEventMetadata.model_validate_json(meta_json)
        except ValidationError as exc:
            raise IntegrityError(f"Invalid INTRUSION_EVENT metadata JSON: {exc}") from exc

        actual_wide_sha256 = hashlib.sha256(wide_bytes).hexdigest()
        if not hmac.compare_digest(actual_wide_sha256, metadata.wide_sha256):
            raise IntegrityError(
                "Chain-of-custody violation: decrypted wide_bytes SHA-256 does not match signed metadata"
            )

        actual_roi_sha256 = hashlib.sha256(roi_bytes).hexdigest()
        if not hmac.compare_digest(actual_roi_sha256, metadata.roi_sha256):
            raise IntegrityError(
                "Chain-of-custody violation: decrypted roi_bytes SHA-256 does not match signed metadata"
            )

        payload: DecryptedPayload = DecryptedIntrusionEvent(
            metadata=metadata,
            wide_bytes=wide_bytes,
            roi_bytes=roi_bytes,
        )
        return DecryptedFrame(header=header, session_epoch=session_epoch, payload=payload)

    control_models: dict[
        MessageType,
        type[EventAckPayload | HeartbeatPayload | FenceSyncPayload | FenceAckPayload],
    ] = {
        MessageType.EVENT_ACK: EventAckPayload,
        MessageType.HEARTBEAT: HeartbeatPayload,
        MessageType.FENCE_SYNC: FenceSyncPayload,
        MessageType.FENCE_ACK: FenceAckPayload,
    }
    model_cls = control_models[header.msg_type]
    try:
        control_payload: DecryptedPayload = model_cls.model_validate_json(plaintext)
    except ValidationError as exc:
        raise IntegrityError(f"Invalid {header.msg_type.name} JSON payload: {exc}") from exc

    return DecryptedFrame(header=header, session_epoch=session_epoch, payload=control_payload)


def validate_replay_watermark(
    *,
    incoming_epoch: int,
    incoming_seq: int,
    last_epoch: int,
    last_seq: int,
    is_known_duplicate_event: bool = False,
) -> bool:
    """Enforce monotonic (session_epoch, seq_counter) replay protection.

    Returns True if the packet is a fresh frame that advances the watermark, or
    False if it is a verified idempotent duplicate retry. Raises ReplayError
    for any stale epoch or non-increasing sequence counter without a known event_id.
    """
    if incoming_epoch < last_epoch:
        raise ReplayError(
            f"Stale session_epoch {incoming_epoch} < last accepted epoch {last_epoch}"
        )

    if incoming_epoch > last_epoch:
        if incoming_seq < 1:
            raise ReplayError(f"Invalid seq_counter {incoming_seq} for new session_epoch")
        return True

    # Same session_epoch
    if incoming_seq <= last_seq:
        if is_known_duplicate_event:
            return False
        raise ReplayError(
            f"Replay detected: seq_counter {incoming_seq} <= last_seq_counter {last_seq}"
        )

    return True
