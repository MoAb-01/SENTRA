-- =============================================================================
-- SENTRA Edge Node — SQLite WAL Transactional Outbox & Local State Schema
-- =============================================================================
-- Guarantees crash-safe local persistence, strictly monotonic sequence counters
-- across reboots, FIFO exponential-backoff delivery, and ring-buffer quota
-- eviction during prolonged WAN blackouts.
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA busy_timeout = 5000;

-- -----------------------------------------------------------------------------
-- 1. Persistent Node Identity & Monotonic Cryptographic Sequence State
--    Single-row table enforced via CHECK (singleton_id = 1).
--    Prevents nonce reuse across process crashes, power loss, or OS reboots.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS node_state (
    singleton_id     INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    node_id          TEXT    NOT NULL CHECK (length(node_id) = 36),
    key_id           INTEGER NOT NULL CHECK (key_id >= 0 AND key_id <= 4294967295),
    session_epoch    INTEGER NOT NULL DEFAULT 1 CHECK (session_epoch >= 0 AND session_epoch <= 4294967295),
    last_seq_counter INTEGER NOT NULL DEFAULT 0 CHECK (last_seq_counter >= 0),
    updated_at       INTEGER NOT NULL CHECK (updated_at > 0)
) STRICT;

-- -----------------------------------------------------------------------------
-- 2. Transactional Outbox for Pre-Encrypted Binary Wire Frames
--    Stores already-sealed AES-256-GCM frames ready for direct WebSocket send.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outbox_events (
    event_id         TEXT    PRIMARY KEY CHECK (length(event_id) = 36),
    seq_counter      INTEGER NOT NULL UNIQUE CHECK (seq_counter > 0),
    state            TEXT    NOT NULL CHECK (state IN ('PENDING', 'IN_FLIGHT', 'ACKED')),
    wire_frame       BLOB    NOT NULL CHECK (length(wire_frame) >= 74),
    frame_size_bytes INTEGER NOT NULL CHECK (frame_size_bytes > 0),
    attempt_count    INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_retry_at    INTEGER NOT NULL CHECK (next_retry_at >= 0),
    created_at       INTEGER NOT NULL CHECK (created_at > 0)
) STRICT;

-- Optimized index for FIFO outbox drain respecting exponential backoff schedule
CREATE INDEX IF NOT EXISTS idx_outbox_fifo_drain
    ON outbox_events (state, next_retry_at, seq_counter);

-- Optimized index for FIFO ring-buffer eviction when total disk quota is exceeded
CREATE INDEX IF NOT EXISTS idx_outbox_ring_eviction
    ON outbox_events (state, created_at, seq_counter);

-- -----------------------------------------------------------------------------
-- 3. Cached Versioned Virtual Fences for Autonomous Offline Boot
--    Allows edge nodes to start enforcing perimeters immediately with zero WAN.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cached_fences (
    fence_id      TEXT    PRIMARY KEY CHECK (length(fence_id) = 36),
    version       INTEGER NOT NULL CHECK (version >= 1),
    name          TEXT    NOT NULL CHECK (length(trim(name)) > 0),
    vertices_json TEXT    NOT NULL CHECK (json_valid(vertices_json)),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    synced_at     INTEGER NOT NULL CHECK (synced_at > 0)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_cached_fences_active_version
    ON cached_fences (is_active, version DESC);
