/**
 * SENTRA v1 Shared TypeScript Data Contracts for the Operations Console.
 * Strictly aligned with WIRE_PROTOCOL_V1.md, packages/protocol-py, and
 * core/db/migrations/001_initial_schema.sql.
 */

export type UUID = string;
export type ISOTimestamp = string;
export type Sha256Hex = string;

/** Normalized 2D coordinate [x, y] in [0.0, 1.0] */
export type NormalizedPoint = readonly [number, number];

/** Normalized bounding box [x, y, w, h] in [0.0, 1.0] */
export type NormalizedBBox = readonly [number, number, number, number];

export type ImageFormat = 'jpeg' | 'webp';

export type UserRole = 'ADMIN' | 'OPERATOR' | 'AUDITOR';

export type NodeStatus = 'ONLINE' | 'DEGRADED' | 'OFFLINE' | 'REVOKED';

export type TriageStatus = 'NEW' | 'ACKNOWLEDGED' | 'FALSE_POSITIVE' | 'ESCALATED';

export type OutboxState = 'PENDING' | 'IN_FLIGHT' | 'ACKED';

export const MessageType = {
  INTRUSION_EVENT: 0x01,
  EVENT_ACK: 0x02,
  HEARTBEAT: 0x03,
  FENCE_SYNC: 0x04,
  FENCE_ACK: 0x05,
} as const;

export type MessageTypeCode = (typeof MessageType)[keyof typeof MessageType];

// -----------------------------------------------------------------------------
// Authentication & RBAC Contracts (Dual-Token Architecture)
// -----------------------------------------------------------------------------

export interface UserProfile {
  readonly user_id: UUID;
  readonly email: string;
  readonly role: UserRole;
  readonly is_active: boolean;
  readonly created_at: ISOTimestamp;
  readonly updated_at: ISOTimestamp;
}

/**
 * Access tokens are short-lived (15-60 min) and held strictly in memory.
 * Refresh tokens are rotated via HttpOnly Secure cookies on Core API routes.
 */
export interface AuthSessionResponse {
  readonly access_token: string;
  readonly token_type: 'Bearer';
  readonly expires_in_seconds: number;
  readonly user: UserProfile;
}

// -----------------------------------------------------------------------------
// Edge Node & Heartbeat Telemetry
// -----------------------------------------------------------------------------

export interface EdgeNode {
  readonly node_id: UUID;
  readonly name: string;
  readonly location: string;
  readonly active_key_id: number;
  readonly last_seq_counter: number;
  readonly last_session_epoch: number;
  readonly status: NodeStatus;
  readonly last_heartbeat_at: ISOTimestamp | null;
  readonly created_at: ISOTimestamp;
  readonly updated_at: ISOTimestamp;
}

export interface HeartbeatTelemetry {
  readonly node_id: UUID;
  readonly uptime_s: number;
  readonly outbox_depth: number;
  readonly outbox_bytes: number;
  readonly active_fence_version: number;
  readonly cpu_temp_c: number | null;
  readonly received_at: ISOTimestamp;
}

// -----------------------------------------------------------------------------
// Virtual Fences (Geofencing Polygons: 3..12 normalized vertices)
// -----------------------------------------------------------------------------

export interface VirtualFence {
  readonly fence_id: UUID;
  readonly node_id: UUID;
  readonly name: string;
  readonly version: number;
  readonly vertices: readonly NormalizedPoint[];
  readonly is_active: boolean;
  readonly created_by: UUID | null;
  readonly created_at: ISOTimestamp;
}

export interface CreateVirtualFenceRequest {
  readonly node_id: UUID;
  readonly name: string;
  readonly vertices: readonly NormalizedPoint[];
  readonly is_active?: boolean;
}

export interface FenceAck {
  readonly fence_id: UUID;
  readonly version: number;
  readonly applied: boolean;
  readonly error: string | null;
}

// -----------------------------------------------------------------------------
// Intrusion Events & Evidence Vault
// -----------------------------------------------------------------------------

export interface IntrusionEventRecord {
  readonly event_id: UUID;
  readonly node_id: UUID;
  readonly seq_counter: number;
  readonly fence_id: UUID | null;
  readonly fence_version: number;
  readonly detected_at: ISOTimestamp;
  readonly received_at: ISOTimestamp;
  readonly confidence: number;
  readonly bbox: NormalizedBBox;
  readonly ground_point: NormalizedPoint;
  readonly persistence_frames: number;
  readonly wide_object_key: string;
  readonly wide_sha256: Sha256Hex;
  readonly roi_object_key: string;
  readonly roi_sha256: Sha256Hex;
  readonly wide_presigned_url?: string;
  readonly roi_presigned_url?: string;
  readonly image_format?: ImageFormat;
  readonly triage_status: TriageStatus;
  readonly expires_at: ISOTimestamp;
}

export interface UpdateEventTriageRequest {
  readonly triage_status: Exclude<TriageStatus, 'NEW'>;
  readonly note?: string;
}

// -----------------------------------------------------------------------------
// Immutable Append-Only Operator Audit Logs
// -----------------------------------------------------------------------------

export interface AuditLogEntry {
  readonly log_id: number;
  readonly actor_user_id: UUID | null;
  readonly action: string;
  readonly target_type: string | null;
  readonly target_id: string | null;
  readonly details: Readonly<Record<string, unknown>>;
  readonly created_at: ISOTimestamp;
}

// -----------------------------------------------------------------------------
// Console Live WebSocket Stream Events (Core -> React Operations Console)
// -----------------------------------------------------------------------------

export type ConsoleWsEvent =
  | {
      readonly type: 'INTRUSION_ALERT';
      readonly data: IntrusionEventRecord;
    }
  | {
      readonly type: 'NODE_HEARTBEAT';
      readonly data: HeartbeatTelemetry;
    }
  | {
      readonly type: 'NODE_STATUS_CHANGED';
      readonly data: {
        readonly node_id: UUID;
        readonly status: NodeStatus;
        readonly updated_at: ISOTimestamp;
      };
    }
  | {
      readonly type: 'FENCE_SYNC_ACK';
      readonly data: FenceAck & { readonly node_id: UUID };
    }
  | {
      readonly type: 'TRIAGE_UPDATED';
      readonly data: {
        readonly event_id: UUID;
        readonly triage_status: TriageStatus;
        readonly actor_user_id: UUID;
        readonly updated_at: ISOTimestamp;
      };
    };
