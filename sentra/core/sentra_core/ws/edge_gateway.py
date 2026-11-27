"""Authenticated binary WebSocket gateway for Edge nodes (/ws/edge/{node_id})."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sentra_protocol.constants import MessageType
from sentra_protocol.crypto import DecryptedIntrusionEvent, open_frame, seal_control_frame
from sentra_protocol.errors import InvalidKeyError, SentraProtocolError
from sentra_protocol.models import (
    EventAckPayload,
    FenceAckPayload,
    FenceSyncPayload,
    HeartbeatPayload,
)

from ..config import CoreConfig
from ..object_store import ObjectStore, build_evidence_keys
from ..repositories.audit_repo import AuditRepository
from ..repositories.events_repo import EventsRepository
from ..repositories.nodes_repo import NodesRepository, ReplayAttackError, VirtualFenceRecord
from ..security import derive_node_key
from .registry import ConnectionRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["edge-ws"])


async def push_fence_sync_to_node(
    *,
    fence: VirtualFenceRecord,
    key_id: int,
    master_key: bytes,
    registry: ConnectionRegistry,
) -> bool:
    """Seal and deliver a signed FENCE_SYNC binary frame to an online edge node."""
    node_key = derive_node_key(master_key, fence.node_id, key_id)
    epoch, seq = await registry.next_server_seq(fence.node_id)
    sync_payload = FenceSyncPayload(
        fence_id=fence.fence_id,
        version=fence.version,
        name=fence.name,
        vertices=fence.vertices,
        is_active=fence.is_active,
    )
    frame = seal_control_frame(
        msg_type=MessageType.FENCE_SYNC,
        node_id=fence.node_id,
        key_id=key_id,
        session_epoch=epoch,
        seq_counter=seq,
        key=node_key,
        payload=sync_payload,
    )
    return await registry.push_to_edge(fence.node_id, frame)


@router.websocket("/ws/edge/{node_id}")
async def edge_websocket_endpoint(ws: WebSocket, node_id: UUID) -> None:
    """Binary wire protocol endpoint for registered SENTRA Edge nodes."""
    config: CoreConfig = ws.app.state.config
    nodes_repo: NodesRepository = ws.app.state.nodes_repo
    events_repo: EventsRepository = ws.app.state.events_repo
    audit_repo: AuditRepository = ws.app.state.audit_repo
    object_store: ObjectStore = ws.app.state.object_store
    registry: ConnectionRegistry = ws.app.state.registry

    node = await nodes_repo.get_node(node_id)
    if node is None or node.status == "REVOKED":
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unknown or revoked node")
        return

    await ws.accept()
    await registry.register_edge(node_id, ws)
    await nodes_repo.update_heartbeat(node_id=node_id, status="ONLINE")
    logger.info("Edge node connected: node_id=%s", node_id)

    def _resolve_node_key(frame_node_id: UUID, key_id: int) -> bytes:
        if frame_node_id != node_id:
            raise InvalidKeyError(
                f"Header node_id ({frame_node_id}) does not match connected path node_id ({node_id})"
            )
        return derive_node_key(config.node_master_key, frame_node_id, key_id)

    try:
        # Immediately sync active fence if node hasn't confirmed the latest version
        active_fence = await nodes_repo.get_active_fence(node_id)
        confirmed_ver = await registry.get_confirmed_fence_version(node_id)
        if active_fence is not None and active_fence.version > confirmed_ver:
            await push_fence_sync_to_node(
                fence=active_fence,
                key_id=node.active_key_id,
                master_key=config.node_master_key,
                registry=registry,
            )

        while True:
            raw_bytes = await ws.receive_bytes()
            try:
                frame = open_frame(raw_bytes, _resolve_node_key)
                payload = frame.payload

                if isinstance(payload, DecryptedIntrusionEvent):
                    await _handle_intrusion_event(
                        ws=ws,
                        node_id=node_id,
                        key_id=frame.header.key_id,
                        session_epoch=frame.session_epoch,
                        seq_counter=frame.header.seq_counter,
                        timestamp_ns=frame.header.timestamp_ns,
                        event=payload,
                        config=config,
                        nodes_repo=nodes_repo,
                        events_repo=events_repo,
                        object_store=object_store,
                        registry=registry,
                    )
                elif isinstance(payload, HeartbeatPayload):
                    await _handle_heartbeat(
                        ws=ws,
                        node_id=node_id,
                        key_id=frame.header.key_id,
                        payload=payload,
                        config=config,
                        nodes_repo=nodes_repo,
                        registry=registry,
                    )
                elif isinstance(payload, FenceAckPayload):
                    if payload.applied:
                        await registry.record_fence_ack(node_id, payload.version)
                    await registry.broadcast_to_consoles(
                        {
                            "type": "FENCE_SYNC_ACK",
                            "data": {
                                "node_id": str(node_id),
                                "fence_id": str(payload.fence_id),
                                "version": payload.version,
                                "applied": payload.applied,
                                "error": payload.error,
                            },
                        }
                    )
            except (SentraProtocolError, ReplayAttackError) as exc:
                logger.warning("Security violation from edge node=%s: %s", node_id, exc)
                await audit_repo.append_log(
                    actor_user_id=None,
                    action="EDGE_SECURITY_VIOLATION",
                    target_type="edge_node",
                    target_id=str(node_id),
                    details={"error_type": type(exc).__name__, "detail": str(exc)},
                )
                await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason=type(exc).__name__)
                return
    except WebSocketDisconnect:
        logger.info("Edge node disconnected: node_id=%s", node_id)
    finally:
        await registry.unregister_edge(node_id, ws)
        await nodes_repo.update_heartbeat(node_id=node_id, status="OFFLINE")


async def _handle_intrusion_event(
    *,
    ws: WebSocket,
    node_id: UUID,
    key_id: int,
    session_epoch: int,
    seq_counter: int,
    timestamp_ns: int,
    event: DecryptedIntrusionEvent,
    config: CoreConfig,
    nodes_repo: NodesRepository,
    events_repo: EventsRepository,
    object_store: ObjectStore,
    registry: ConnectionRegistry,
) -> None:
    meta = event.metadata
    replay_check = await nodes_repo.check_replay_for_event(
        node_id=node_id,
        session_epoch=session_epoch,
        seq_counter=seq_counter,
        event_id=meta.event_id,
    )

    created = False
    stored_row = None

    if not replay_check.is_duplicate_event:
        detected_at = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)
        expires_at = detected_at + timedelta(days=config.evidence_retention_days)
        wide_key, roi_key = build_evidence_keys(
            node_id=node_id,
            detected_at=detected_at,
            event_id=meta.event_id,
            image_format=meta.image_format,
        )

        # Durability Rule: Upload evidence to MinIO BEFORE PostgreSQL commit & ACK
        await object_store.put_evidence(
            object_key=wide_key,
            data=event.wide_bytes,
            image_format=meta.image_format,
        )
        await object_store.put_evidence(
            object_key=roi_key,
            data=event.roi_bytes,
            image_format=meta.image_format,
        )

        stored_row, created = await events_repo.insert_event_idempotent(
            event_id=meta.event_id,
            node_id=node_id,
            session_epoch=session_epoch,
            seq_counter=seq_counter,
            fence_id=meta.fence_id,
            fence_version=meta.fence_version,
            detected_at=detected_at,
            confidence=meta.confidence,
            bbox=meta.bbox,
            ground_point=meta.ground_point,
            persistence_frames=meta.persistence_frames,
            wide_object_key=wide_key,
            wide_sha256=meta.wide_sha256,
            roi_object_key=roi_key,
            roi_sha256=meta.roi_sha256,
            expires_at=expires_at,
        )

    # Emit EVENT_ACK strictly AFTER object storage + PostgreSQL commit succeed
    ack_status = "ACCEPTED" if created else "DUPLICATE"
    srv_epoch, srv_seq = await registry.next_server_seq(node_id)
    node_key = derive_node_key(config.node_master_key, node_id, key_id)
    ack_frame = seal_control_frame(
        msg_type=MessageType.EVENT_ACK,
        node_id=node_id,
        key_id=key_id,
        session_epoch=srv_epoch,
        seq_counter=srv_seq,
        key=node_key,
        payload=EventAckPayload(
            event_id=meta.event_id,
            seq_counter=seq_counter,
            status=ack_status,
            received_at_ns=time.time_ns(),
        ),
    )
    await ws.send_bytes(ack_frame)

    if created and stored_row is not None:
        wide_url = await object_store.generate_presigned_url(
            stored_row.wide_object_key, expires_in_sec=config.presigned_ttl_sec
        )
        roi_url = await object_store.generate_presigned_url(
            stored_row.roi_object_key, expires_in_sec=config.presigned_ttl_sec
        )
        await registry.broadcast_to_consoles(
            {
                "type": "INTRUSION_ALERT",
                "data": stored_row.to_payload_dict(
                    wide_presigned_url=wide_url,
                    roi_presigned_url=roi_url,
                ),
            }
        )


async def _handle_heartbeat(
    *,
    ws: WebSocket,
    node_id: UUID,
    key_id: int,
    payload: HeartbeatPayload,
    config: CoreConfig,
    nodes_repo: NodesRepository,
    registry: ConnectionRegistry,
) -> None:
    await nodes_repo.update_heartbeat(node_id=node_id, status="ONLINE")
    srv_epoch, srv_seq = await registry.next_server_seq(node_id)
    node_key = derive_node_key(config.node_master_key, node_id, key_id)
    pong = seal_control_frame(
        msg_type=MessageType.HEARTBEAT,
        node_id=node_id,
        key_id=key_id,
        session_epoch=srv_epoch,
        seq_counter=srv_seq,
        key=node_key,
        payload=payload,
    )
    await ws.send_bytes(pong)
    await registry.broadcast_to_consoles(
        {
            "type": "NODE_HEARTBEAT",
            "data": {
                "node_id": str(node_id),
                "uptime_s": payload.uptime_s,
                "outbox_depth": payload.outbox_depth,
                "outbox_bytes": payload.outbox_bytes,
                "active_fence_version": payload.active_fence_version,
                "cpu_temp_c": payload.cpu_temp_c,
                "received_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
