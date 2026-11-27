"""Wire protocol constants and message type definitions for SENTRA v1."""

from __future__ import annotations

import struct
from enum import IntEnum

PROTOCOL_MAGIC: bytes = b"SNTR"
PROTOCOL_VERSION: int = 0x01

# Big-endian fixed wire header:
# magic(4s) version(B) msg_type(B) node_id(16s) key_id(I)
# seq_counter(Q) timestamp_ns(Q) nonce(12s) payload_len(I)
HEADER_FORMAT: str = "!4sBB16sIQQ12sI"
HEADER_STRUCT: struct.Struct = struct.Struct(HEADER_FORMAT)
HEADER_SIZE: int = HEADER_STRUCT.size  # 58 bytes

# Exact 42-byte prefix (magic through timestamp_ns) bound as AES-256-GCM AAD
AAD_SIZE: int = 42

# Deterministic 12-byte AES-GCM nonce: [session_epoch (uint32) || seq_counter (uint64)]
NONCE_FORMAT: str = "!IQ"
NONCE_STRUCT: struct.Struct = struct.Struct(NONCE_FORMAT)
NONCE_SIZE: int = NONCE_STRUCT.size  # 12 bytes

# Length prefix for inner binary INTRUSION_EVENT container sections
LENGTH_PREFIX_FORMAT: str = "!I"
LENGTH_PREFIX_STRUCT: struct.Struct = struct.Struct(LENGTH_PREFIX_FORMAT)
LENGTH_PREFIX_SIZE: int = LENGTH_PREFIX_STRUCT.size  # 4 bytes

# Cryptographic sizes
AES_256_KEY_SIZE: int = 32
GCM_TAG_SIZE: int = 16

# DoS protection bounds
MAX_PAYLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MiB (ciphertext + 16-byte tag)
MAX_PLAINTEXT_SIZE: int = MAX_PAYLOAD_SIZE - GCM_TAG_SIZE
MIN_PAYLOAD_SIZE: int = GCM_TAG_SIZE
MIN_FRAME_SIZE: int = HEADER_SIZE + MIN_PAYLOAD_SIZE  # 74 bytes
MAX_FRAME_SIZE: int = HEADER_SIZE + MAX_PAYLOAD_SIZE

# Unsigned integer limits
UINT32_MAX: int = 0xFFFFFFFF
UINT64_MAX: int = 0xFFFFFFFFFFFFFFFF

# Virtual fence geometry bounds
MIN_FENCE_VERTICES: int = 3
MAX_FENCE_VERTICES: int = 12
MIN_POLYGON_AREA: float = 1e-6


class MessageType(IntEnum):
    """SENTRA v1 wire protocol message types."""

    INTRUSION_EVENT = 0x01  # Edge -> Core
    EVENT_ACK = 0x02        # Core -> Edge
    HEARTBEAT = 0x03        # Bidirectional
    FENCE_SYNC = 0x04       # Core -> Edge
    FENCE_ACK = 0x05        # Edge -> Core
