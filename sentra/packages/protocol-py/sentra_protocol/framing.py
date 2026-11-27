"""Binary wire framing, header packing/unpacking, and container serialization."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .constants import (
    AAD_SIZE,
    HEADER_SIZE,
    HEADER_STRUCT,
    LENGTH_PREFIX_SIZE,
    LENGTH_PREFIX_STRUCT,
    MAX_FRAME_SIZE,
    MAX_PAYLOAD_SIZE,
    MIN_PAYLOAD_SIZE,
    NONCE_SIZE,
    NONCE_STRUCT,
    PROTOCOL_MAGIC,
    PROTOCOL_VERSION,
    UINT32_MAX,
    UINT64_MAX,
    MessageType,
)
from .errors import (
    IntegrityError,
    MalformedFrameError,
    OversizedFrameError,
    TruncatedFrameError,
    UnknownMessageTypeError,
    UnsupportedVersionError,
)


@dataclass(frozen=True, slots=True)
class FrameHeader:
    """Decoded 58-byte SENTRA v1 binary wire header."""

    magic: bytes
    version: int
    msg_type: MessageType
    node_id: UUID
    key_id: int
    seq_counter: int
    timestamp_ns: int
    nonce: bytes
    payload_len: int


@dataclass(frozen=True, slots=True)
class ParsedFrame:
    """Parsed wire frame prior to AES-256-GCM decryption."""

    header: FrameHeader
    aad: bytes
    ciphertext_and_tag: bytes


def derive_nonce(session_epoch: int, seq_counter: int) -> bytes:
    """Derive the deterministic 12-byte AES-GCM nonce: [uint32 session_epoch || uint64 seq_counter]."""
    if not (0 <= session_epoch <= UINT32_MAX):
        raise ValueError(f"session_epoch out of uint32 range: {session_epoch}")
    if not (1 <= seq_counter <= UINT64_MAX):
        raise ValueError(f"seq_counter must be in [1, 2^64-1], got {seq_counter}")
    return NONCE_STRUCT.pack(session_epoch, seq_counter)


def parse_nonce(nonce: bytes) -> tuple[int, int]:
    """Unpack deterministic 12-byte nonce into (session_epoch, seq_counter)."""
    if len(nonce) != NONCE_SIZE:
        raise MalformedFrameError(f"Nonce must be {NONCE_SIZE} bytes, got {len(nonce)}")
    session_epoch, seq_counter = NONCE_STRUCT.unpack(nonce)
    return int(session_epoch), int(seq_counter)


def pack_header(
    *,
    msg_type: MessageType,
    node_id: UUID,
    key_id: int,
    seq_counter: int,
    timestamp_ns: int,
    nonce: bytes,
    payload_len: int,
) -> bytes:
    """Pack a validated 58-byte SENTRA v1 wire header in network byte order."""
    if not isinstance(msg_type, MessageType):
        raise UnknownMessageTypeError(f"Invalid message type: {msg_type!r}")
    if not (0 <= key_id <= UINT32_MAX):
        raise ValueError(f"key_id out of uint32 range: {key_id}")
    if not (1 <= seq_counter <= UINT64_MAX):
        raise ValueError(f"seq_counter must be in [1, 2^64-1], got {seq_counter}")
    if not (0 <= timestamp_ns <= UINT64_MAX):
        raise ValueError(f"timestamp_ns out of uint64 range: {timestamp_ns}")
    if len(nonce) != NONCE_SIZE:
        raise MalformedFrameError(f"Nonce must be {NONCE_SIZE} bytes, got {len(nonce)}")
    if payload_len < MIN_PAYLOAD_SIZE:
        raise MalformedFrameError(
            f"payload_len ({payload_len}) is smaller than minimum GCM tag size ({MIN_PAYLOAD_SIZE})"
        )
    if payload_len > MAX_PAYLOAD_SIZE:
        raise OversizedFrameError(
            f"payload_len ({payload_len}) exceeds MAX_PAYLOAD_SIZE ({MAX_PAYLOAD_SIZE})"
        )

    return HEADER_STRUCT.pack(
        PROTOCOL_MAGIC,
        PROTOCOL_VERSION,
        int(msg_type),
        node_id.bytes,
        key_id,
        seq_counter,
        timestamp_ns,
        nonce,
        payload_len,
    )


def unpack_frame(raw_frame: bytes) -> ParsedFrame:
    """Validate framing bounds and unpack the 58-byte header, 42-byte AAD, and ciphertext+tag."""
    frame_len = len(raw_frame)
    if frame_len > MAX_FRAME_SIZE:
        raise OversizedFrameError(
            f"Raw frame length ({frame_len}) exceeds MAX_FRAME_SIZE ({MAX_FRAME_SIZE})"
        )
    if frame_len < HEADER_SIZE:
        raise TruncatedFrameError(
            f"Raw frame length ({frame_len}) is smaller than fixed header size ({HEADER_SIZE})"
        )

    (
        magic,
        version,
        raw_msg_type,
        node_id_bytes,
        key_id,
        seq_counter,
        timestamp_ns,
        nonce,
        payload_len,
    ) = HEADER_STRUCT.unpack_from(raw_frame, 0)

    if magic != PROTOCOL_MAGIC:
        raise MalformedFrameError(f"Invalid protocol magic: {magic!r}, expected {PROTOCOL_MAGIC!r}")

    if version != PROTOCOL_VERSION:
        raise UnsupportedVersionError(
            f"Unsupported protocol version: 0x{version:02x}, expected 0x{PROTOCOL_VERSION:02x}"
        )

    try:
        msg_type = MessageType(raw_msg_type)
    except ValueError as exc:
        raise UnknownMessageTypeError(f"Unknown message type: 0x{raw_msg_type:02x}") from exc

    if payload_len > MAX_PAYLOAD_SIZE:
        raise OversizedFrameError(
            f"Declared payload_len ({payload_len}) exceeds MAX_PAYLOAD_SIZE ({MAX_PAYLOAD_SIZE})"
        )

    if payload_len < MIN_PAYLOAD_SIZE:
        raise MalformedFrameError(
            f"Declared payload_len ({payload_len}) is smaller than GCM tag size ({MIN_PAYLOAD_SIZE})"
        )

    expected_total = HEADER_SIZE + payload_len
    if frame_len < expected_total:
        raise TruncatedFrameError(
            f"Truncated frame: expected {expected_total} bytes (header + payload), got {frame_len}"
        )
    if frame_len > expected_total:
        raise MalformedFrameError(
            f"Trailing bytes after payload: expected {expected_total} bytes, got {frame_len}"
        )

    header = FrameHeader(
        magic=magic,
        version=version,
        msg_type=msg_type,
        node_id=UUID(bytes=node_id_bytes),
        key_id=key_id,
        seq_counter=seq_counter,
        timestamp_ns=timestamp_ns,
        nonce=nonce,
        payload_len=payload_len,
    )

    aad = bytes(raw_frame[:AAD_SIZE])
    ciphertext_and_tag = bytes(raw_frame[HEADER_SIZE:expected_total])
    return ParsedFrame(header=header, aad=aad, ciphertext_and_tag=ciphertext_and_tag)


def pack_intrusion_container(metadata_json: bytes, wide_bytes: bytes, roi_bytes: bytes) -> bytes:
    """Pack [meta_len|meta_json|wide_len|wide_bytes|roi_len|roi_bytes] binary container."""
    if not metadata_json:
        raise ValueError("metadata_json must not be empty")
    if not wide_bytes:
        raise ValueError("wide_bytes must not be empty")
    if not roi_bytes:
        raise ValueError("roi_bytes must not be empty")

    return b"".join(
        (
            LENGTH_PREFIX_STRUCT.pack(len(metadata_json)),
            metadata_json,
            LENGTH_PREFIX_STRUCT.pack(len(wide_bytes)),
            wide_bytes,
            LENGTH_PREFIX_STRUCT.pack(len(roi_bytes)),
            roi_bytes,
        )
    )


def unpack_intrusion_container(plaintext: bytes) -> tuple[bytes, bytes, bytes]:
    """Unpack and bounds-check the decrypted INTRUSION_EVENT binary container."""
    total_len = len(plaintext)
    offset = 0

    def _read_chunk(label: str) -> bytes:
        nonlocal offset
        if offset + LENGTH_PREFIX_SIZE > total_len:
            raise IntegrityError(f"Truncated length prefix for {label} at offset {offset}")
        (chunk_len,) = LENGTH_PREFIX_STRUCT.unpack_from(plaintext, offset)
        offset += LENGTH_PREFIX_SIZE
        if chunk_len == 0:
            raise IntegrityError(f"Empty {label} chunk in INTRUSION_EVENT container")
        if offset + chunk_len > total_len:
            raise IntegrityError(
                f"Truncated {label} chunk: declared {chunk_len} bytes, only {total_len - offset} available"
            )
        chunk = plaintext[offset : offset + chunk_len]
        offset += chunk_len
        return chunk

    meta_json = _read_chunk("metadata_json")
    wide_bytes = _read_chunk("wide_bytes")
    roi_bytes = _read_chunk("roi_bytes")

    if offset != total_len:
        raise IntegrityError(
            f"Unexpected trailing bytes in INTRUSION_EVENT container: {total_len - offset} extra bytes"
        )

    return meta_json, wide_bytes, roi_bytes
