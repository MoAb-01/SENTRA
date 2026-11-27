# SENTRA Binary Wire Protocol Specification — v1 (`SNTR`)

**Status:** Authoritative Production Contract  
**Protocol Version:** `0x01`  
**Byte Order:** Big-Endian (Network Byte Order, `!`)  
**Cipher Suite:** AES-256-GCM (AEAD, 256-bit key, 96-bit nonce, 128-bit authentication tag)  
**Digest Algorithm:** SHA-256 (FIPS 180-4)

---

## 1. Design Goals

1. **Zero Base64 Overhead:** Binary media payloads (`wide_bytes`, `roi_bytes`) are transmitted inside a length-prefixed binary container prior to AES-256-GCM encryption, eliminating the ~33% Base64 expansion overhead and preserving the `>95%` WAN bandwidth reduction budget.
2. **Header Integrity & Anti-Spoofing (AAD):** Every routing, identity, sequence, and timestamp field in the 42-byte header prefix is bound cryptographically as AES-256-GCM Additional Authenticated Data (AAD).
3. **Mathematical Nonce Uniqueness:** Nonces are deterministically derived from `[session_epoch || seq_counter]`, strictly persisted across reboots in SQLite WAL (`PRAGMA synchronous = FULL`), eliminating random-nonce collision risk and reboot reuse.
4. **End-to-End Chain of Custody:** Decrypted media buffers are independently hashed (SHA-256) by Core and compared in constant time against the authenticated metadata digests before ingestion into MinIO and PostgreSQL.
5. **DoS Resistance:** Strict payload size caps (`MAX_PAYLOAD_SIZE = 10 MiB`), exact frame-length framing validation, and early rejection of invalid magic/version/message types prevent memory exhaustion.

---

## 2. Binary Frame Layout (Big-Endian)

Struct format string: `!4sBB16sIQQ12sI` (`58` bytes fixed header).

| Offset | Length (B) | Field | Type | Description |
|---:|---:|---|---|---|
| `0` | `4` | `magic` | `bytes[4]` | Constant ASCII magic `b"SNTR"` (`0x53 0x4E 0x54 0x52`) |
| `4` | `1` | `version` | `uint8` | Protocol version `0x01` |
| `5` | `1` | `msg_type` | `uint8` | Message type enum (see §3) |
| `6` | `16` | `node_id` | `bytes[16]` | Raw 128-bit UUIDv4 bytes identifying the edge node |
| `22` | `4` | `key_id` | `uint32` | Active pre-shared symmetric key identifier (key rotation) |
| `26` | `8` | `seq_counter` | `uint64` | Strictly monotonic per-node sequence counter (`>= 1`) |
| `34` | `8` | `timestamp_ns` | `uint64` | UTC Unix epoch timestamp in nanoseconds |
| `42` | `12` | `nonce` | `bytes[12]` | Deterministic AES-GCM nonce: `[session_epoch (4B uint32) \|\| seq_counter (8B uint64)]` |
| `54` | `4` | `payload_len` | `uint32` | Exact byte length of `ciphertext_and_tag` (`16 <= payload_len <= 10,485,760`) |
| `58` | `payload_len` | `ciphertext_and_tag` | `bytes[payload_len]` | `AES-256-GCM(plaintext)` concatenated with its trailing 16-byte authentication tag |

### Frame Bounds
- **Minimum Frame Size:** `58 + 16 = 74` bytes (header + 16-byte GCM tag for an empty plaintext).
- **Maximum Payload Size:** `10 * 1024 * 1024` bytes (`10,485,760` bytes, ciphertext + 16-byte tag).
- **Maximum Total Frame Size:** `58 + 10,485,760 = 10,485,818` bytes.
- Frames shorter than `58` bytes, frames where `len(frame) != 58 + payload_len`, or frames with `payload_len < 16` or `payload_len > 10,485,760` MUST be rejected immediately before cryptographic key lookup or decryption.

---

## 3. Message Types (`msg_type`)

| Value | Name | Direction | Plaintext Encoding |
|---:|---|---|---|
| `0x01` | `INTRUSION_EVENT` | Edge → Core | Binary length-prefixed container (see §6) |
| `0x02` | `EVENT_ACK` | Core → Edge | UTF-8 JSON object |
| `0x03` | `HEARTBEAT` | Bidirectional | UTF-8 JSON object |
| `0x04` | `FENCE_SYNC` | Core → Edge | UTF-8 JSON object |
| `0x05` | `FENCE_ACK` | Edge → Core | UTF-8 JSON object |

Any unrecognized `msg_type` MUST raise an explicit protocol error.

---

## 4. Deterministic Nonce Construction

To mathematically eliminate nonce reuse under a given `(node_id, key_id)` pair:

```text
nonce (12 bytes) = struct.pack("!IQ", session_epoch, seq_counter)
```

- `session_epoch` (`uint32`, 4 bytes): Persisted in `node_state.session_epoch` on the edge node. Incremented on crash recovery or manual key/state re-initialization.
- `seq_counter` (`uint64`, 8 bytes): Strictly monotonic counter persisted in `node_state.last_seq_counter` via SQLite WAL (`PRAGMA synchronous = FULL`) in the same transaction as the `outbox_events` insert.
- Key rotation (`key_id` increment) MUST be triggered before `seq_counter` approaches `2^64 - 1` or `session_epoch` approaches `2^32 - 1` (recommended operational cap: `2^31` messages per key).
- Upon successful decryption, receivers MUST additionally verify that the trailing 8 bytes of `nonce` equal `header.seq_counter`.

---

## 5. Additional Authenticated Data (AAD) Binding Rule

The exact **42-byte header prefix** (`raw_frame[0:42]`), covering:

```text
magic (4B) || version (1B) || msg_type (1B) || node_id (16B) || key_id (4B) || seq_counter (8B) || timestamp_ns (8B)
```

MUST be passed verbatim as the `associated_data` (`AAD`) parameter to `AESGCM(key).encrypt(nonce, plaintext, aad)` and `AESGCM(key).decrypt(nonce, ciphertext_and_tag, aad)`.

**Security Property:** Flipping even 1 bit in `magic`, `version`, `msg_type`, `node_id`, `key_id`, `seq_counter`, or `timestamp_ns` invalidates the 128-bit GCM authentication tag and causes decryption to fail with `AuthenticationError`.

---

## 6. Encrypted `INTRUSION_EVENT` (`0x01`) Plaintext Container

Inside the decrypted plaintext of an `INTRUSION_EVENT` frame lies a deterministic, length-prefixed binary container (Big-Endian):

| Order | Field | Type | Description |
|---:|---|---|---|
| 1 | `meta_len` | `uint32` (4B) | Byte length of UTF-8 JSON metadata |
| 2 | `meta_json` | `bytes[meta_len]` | UTF-8 encoded JSON metadata object (see §6.1) |
| 3 | `wide_len` | `uint32` (4B) | Byte length of wide-scene image buffer (`>= 1`) |
| 4 | `wide_bytes` | `bytes[wide_len]` | Raw JPEG or WebP bytes of full-frame context |
| 5 | `roi_len` | `uint32` (4B) | Byte length of upper-body RoI crop buffer (`>= 1`) |
| 6 | `roi_bytes` | `bytes[roi_len]` | Raw JPEG or WebP bytes of `[y : y + 0.35h, x : x + w]` crop |

Trailing bytes after `roi_bytes` are forbidden and MUST be rejected as malformed.

### 6.1 `meta_json` Schema

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "fence_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "fence_version": 3,
  "confidence": 0.94,
  "bbox": [0.42, 0.31, 0.14, 0.48],
  "ground_point": [0.49, 0.79],
  "persistence_frames": 3,
  "wide_sha256": "<64-char lowercase hex SHA-256 of wide_bytes>",
  "roi_sha256": "<64-char lowercase hex SHA-256 of roi_bytes>",
  "image_format": "webp"
}
```

- Coordinates in `bbox` (`[x, y, w, h]`) and `ground_point` (`[xb, yb]`) are normalized to `[0.0, 1.0]`.
- `image_format` MUST be `"jpeg"` or `"webp"`.
- `persistence_frames` MUST be `>= 1`.

---

## 7. Control & Synchronization Plaintext Payloads (`0x02`–`0x05`)

All control frames (`EVENT_ACK`, `HEARTBEAT`, `FENCE_SYNC`, `FENCE_ACK`) are AES-256-GCM encrypted using the exact same 58-byte header and 42-byte AAD rule, with a UTF-8 JSON object as plaintext:

- **`0x02 EVENT_ACK`:** `{ "event_id": UUID, "seq_counter": uint64, "status": "ACCEPTED" | "DUPLICATE", "received_at_ns": uint64 }`
- **`0x03 HEARTBEAT`:** `{ "uptime_s": uint64, "outbox_depth": uint32, "outbox_bytes": uint64, "active_fence_version": uint32, "cpu_temp_c": float | null }`
- **`0x04 FENCE_SYNC`:** `{ "fence_id": UUID, "version": uint32, "name": string, "vertices": [[x, y], ...], "is_active": bool }` (3 to 12 normalized vertices, non-degenerate polygon)
- **`0x05 FENCE_ACK`:** `{ "fence_id": UUID, "version": uint32, "applied": bool, "error": string | null }`

---

## 8. Replay Protection & Chain-of-Custody Verification

1. **Monotonic Sequence Verification (Core):**
   - Core persists `edge_nodes.last_seq_counter` and `edge_nodes.last_session_epoch`.
   - For incoming `INTRUSION_EVENT` frames under the same `session_epoch`, Core MUST reject any packet where `seq_counter <= edge_nodes.last_seq_counter` unless an identical `event_id` already exists in `intrusion_events` (idempotent retry handled via `INSERT ... ON CONFLICT (event_id) DO NOTHING` returning `EVENT_ACK` with `status = "DUPLICATE"`).
   - If `session_epoch < edge_nodes.last_session_epoch`, Core MUST reject the frame immediately as a stale replay (`ReplayError`).
   - If `session_epoch > edge_nodes.last_session_epoch`, `seq_counter` MUST be `>= 1` and Core atomically advances both `last_session_epoch` and `last_seq_counter`.

2. **Chain-of-Custody Media Digest Verification (Core):**
   - Immediately after AES-256-GCM decryption and container unpacking, Core MUST compute:
     - `actual_wide_sha256 = SHA-256(wide_bytes).hexdigest()`
     - `actual_roi_sha256 = SHA-256(roi_bytes).hexdigest()`
   - Core MUST compare both digests in constant time (`hmac.compare_digest`) against `metadata.wide_sha256` and `metadata.roi_sha256`.
   - Any mismatch MUST abort ingestion, raise `IntegrityError`, and emit a security audit log entry.
