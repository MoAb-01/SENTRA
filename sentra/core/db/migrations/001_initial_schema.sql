-- =============================================================================
-- SENTRA Core — PostgreSQL 16 Initial Production Schema (Migration 001)
-- =============================================================================
-- Defines RBAC users, dual-token refresh sessions, registered edge nodes,
-- versioned JSONB geofences, idempotent intrusion events with SHA-256 chain of
-- custody, and trigger-enforced immutable audit logs.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;

-- -----------------------------------------------------------------------------
-- 1. Users & Role-Based Access Control (RBAC)
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    user_id       UUID        PRIMARY KEY,
    email         CITEXT      NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,
    role          TEXT        NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR', 'AUDITOR')),
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 2. Dual-Token Refresh Sessions (Rotation, Sliding Expiration, Revocation)
-- -----------------------------------------------------------------------------
CREATE TABLE refresh_tokens (
    token_id            UUID        PRIMARY KEY,
    user_id             UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_family_id     UUID        NOT NULL,
    token_hash          CHAR(64)    NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    issued_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sliding_expires_at  TIMESTAMPTZ NOT NULL,
    absolute_expires_at TIMESTAMPTZ NOT NULL,
    rotated_at          TIMESTAMPTZ,
    revoked_at          TIMESTAMPTZ,
    revoked_reason      TEXT,
    CHECK (sliding_expires_at <= absolute_expires_at)
);

CREATE INDEX idx_refresh_tokens_user_active
    ON refresh_tokens (user_id, revoked_at)
    WHERE revoked_at IS NULL;

CREATE INDEX idx_refresh_tokens_family
    ON refresh_tokens (token_family_id);

-- -----------------------------------------------------------------------------
-- 3. Registered Edge Nodes & Replay-Protection Watermarks
-- -----------------------------------------------------------------------------
CREATE TABLE edge_nodes (
    node_id            UUID        PRIMARY KEY,
    name               TEXT        NOT NULL CHECK (length(trim(name)) > 0),
    location           TEXT        NOT NULL DEFAULT '',
    active_key_id      INTEGER     NOT NULL DEFAULT 1 CHECK (active_key_id >= 0),
    last_seq_counter   BIGINT      NOT NULL DEFAULT 0 CHECK (last_seq_counter >= 0),
    last_session_epoch INTEGER     NOT NULL DEFAULT 0 CHECK (last_session_epoch >= 0),
    status             TEXT        NOT NULL DEFAULT 'OFFLINE'
                                   CHECK (status IN ('ONLINE', 'DEGRADED', 'OFFLINE', 'REVOKED')),
    last_heartbeat_at  TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_edge_nodes_status
    ON edge_nodes (status, last_heartbeat_at DESC);

-- -----------------------------------------------------------------------------
-- 4. Versioned Virtual Fences (Normalized JSONB Polygons: 3..12 Vertices)
-- -----------------------------------------------------------------------------
CREATE TABLE virtual_fences (
    fence_id   UUID        PRIMARY KEY,
    node_id    UUID        NOT NULL REFERENCES edge_nodes(node_id) ON DELETE CASCADE,
    name       TEXT        NOT NULL DEFAULT 'Primary Perimeter' CHECK (length(trim(name)) > 0),
    version    INTEGER     NOT NULL CHECK (version >= 1),
    vertices   JSONB       NOT NULL CHECK (
                   jsonb_typeof(vertices) = 'array'
                   AND jsonb_array_length(vertices) BETWEEN 3 AND 12
               ),
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_by UUID        REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (node_id, version)
);

CREATE INDEX idx_virtual_fences_node_active
    ON virtual_fences (node_id, version DESC)
    WHERE is_active = TRUE;

-- -----------------------------------------------------------------------------
-- 5. Intrusion Events (Idempotent Ingest, SHA-256 Custody & Retention Purge)
-- -----------------------------------------------------------------------------
CREATE TABLE intrusion_events (
    event_id           UUID        PRIMARY KEY,
    node_id            UUID        NOT NULL REFERENCES edge_nodes(node_id) ON DELETE RESTRICT,
    seq_counter        BIGINT      NOT NULL CHECK (seq_counter > 0),
    fence_id           UUID        REFERENCES virtual_fences(fence_id) ON DELETE SET NULL,
    fence_version      INTEGER     NOT NULL CHECK (fence_version >= 1),
    detected_at        TIMESTAMPTZ NOT NULL,
    received_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confidence         REAL        NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    bbox               JSONB       NOT NULL CHECK (
                           jsonb_typeof(bbox) = 'array'
                           AND jsonb_array_length(bbox) = 4
                       ),
    ground_point       JSONB       NOT NULL CHECK (
                           jsonb_typeof(ground_point) = 'array'
                           AND jsonb_array_length(ground_point) = 2
                       ),
    persistence_frames SMALLINT    NOT NULL CHECK (persistence_frames >= 1),
    wide_object_key    TEXT        NOT NULL CHECK (length(trim(wide_object_key)) > 0),
    wide_sha256        CHAR(64)    NOT NULL CHECK (wide_sha256 ~ '^[0-9a-f]{64}$'),
    roi_object_key     TEXT        NOT NULL CHECK (length(trim(roi_object_key)) > 0),
    roi_sha256         CHAR(64)    NOT NULL CHECK (roi_sha256 ~ '^[0-9a-f]{64}$'),
    triage_status      TEXT        NOT NULL DEFAULT 'NEW'
                                   CHECK (triage_status IN ('NEW', 'ACKNOWLEDGED', 'FALSE_POSITIVE', 'ESCALATED')),
    expires_at         TIMESTAMPTZ NOT NULL,
    UNIQUE (node_id, seq_counter)
);

CREATE INDEX idx_intrusion_events_node_detected
    ON intrusion_events (node_id, detected_at DESC);

CREATE INDEX idx_intrusion_events_triage_received
    ON intrusion_events (triage_status, received_at DESC);

CREATE INDEX idx_intrusion_events_expires_at
    ON intrusion_events (expires_at);

-- -----------------------------------------------------------------------------
-- 6. Immutable Append-Only Audit Logs (Trigger-Protected)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    log_id        BIGSERIAL   PRIMARY KEY,
    actor_user_id UUID        REFERENCES users(user_id) ON DELETE SET NULL,
    action        TEXT        NOT NULL CHECK (length(trim(action)) > 0),
    target_type   TEXT,
    target_id     TEXT,
    details       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_created_at
    ON audit_logs (created_at DESC);

CREATE INDEX idx_audit_logs_actor
    ON audit_logs (actor_user_id, created_at DESC);

CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is strictly append-only; % operations are prohibited', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$;

CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_mutation();

COMMIT;
