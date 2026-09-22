from datetime import datetime, timezone

import pytest

from app.schemas.offline import (
    ConflictResolutionRequest,
    OfflineOperationRequest,
    ScopeRevocationRequest,
    SyncBatchRequest,
    SyncStatus,
)
from app.services.offline import OfflineSyncService


def make_operation(
    tenant_id="tenant-1",
    operation_id="op-1",
    entity_id="issue-1",
    scope_version="v1",
    idempotency_key=None,
    payload=None,
):
    return OfflineOperationRequest(
        tenant_id=tenant_id,
        actor_id="user-1",
        operation_id=operation_id,
        entity_type="issue",
        entity_id=entity_id,
        operation="update",
        payload=payload or {"status": "In Progress"},
        client_timestamp=datetime.now(timezone.utc),
        idempotency_key=idempotency_key or operation_id,
        scope_version=scope_version,
    )


def make_sync_request(
    tenant_id="tenant-1",
    actor_id="user-1",
    scope_version="v1",
    max_operations=50,
):
    return SyncBatchRequest(
        tenant_id=tenant_id,
        actor_id=actor_id,
        scope_version=scope_version,
        max_operations=max_operations,
    )


def test_enqueue_operation():
    service = OfflineSyncService()

    result = service.enqueue(make_operation())

    assert result.operation_id == "op-1"
    assert result.status == SyncStatus.PENDING
    assert result.sequence_number == 1


def test_idempotency_prevents_duplicate_operation():
    service = OfflineSyncService()

    first = service.enqueue(
        make_operation(
            operation_id="op-1",
            idempotency_key="same-key",
        )
    )

    second = service.enqueue(
        make_operation(
            operation_id="op-2",
            idempotency_key="same-key",
        )
    )

    assert second.operation_id == first.operation_id
    assert second.sequence_number == first.sequence_number


def test_operations_are_processed_in_sequence_order():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            operation_id="op-1",
            entity_id="issue-1",
        )
    )

    service.enqueue(
        make_operation(
            operation_id="op-2",
            entity_id="issue-2",
        )
    )

    result = service.sync(make_sync_request())

    assert result.accepted_count == 2
    assert result.operations[0].operation_id == "op-1"
    assert result.operations[1].operation_id == "op-2"

    assert result.operations[0].status == SyncStatus.ACCEPTED
    assert result.operations[1].status == SyncStatus.ACCEPTED


def test_sync_is_resumable_with_max_operations():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            operation_id="op-1",
            entity_id="issue-1",
        )
    )

    service.enqueue(
        make_operation(
            operation_id="op-2",
            entity_id="issue-2",
        )
    )

    first = service.sync(
        make_sync_request(max_operations=1)
    )

    assert first.accepted_count == 1
    assert first.pending_count == 1

    second = service.sync(
        make_sync_request(max_operations=1)
    )

    assert second.accepted_count == 1
    assert second.pending_count == 0


def test_version_conflict_is_detected():
    service = OfflineSyncService()

    operation = make_operation(
        operation_id="op-conflict",
        entity_id="issue-1",
        payload={
            "status": "Resolved",
            "expected_server_version": "v1",
        },
    )

    service.enqueue(operation)

    entity_key = "tenant-1:issue:issue-1"
    service._entity_versions[entity_key] = "v2"

    result = service.sync(make_sync_request())

    assert result.conflict_count == 1
    assert result.operations[0].status == SyncStatus.CONFLICT
    assert (
        result.operations[0].conflict_reason
        == "server_version_changed"
    )


def test_retry_client_resolves_conflict_to_pending():
    service = OfflineSyncService()

    operation = make_operation(
        operation_id="op-retry",
        entity_id="issue-1",
        payload={
            "status": "Resolved",
            "expected_server_version": "v1",
        },
    )

    service.enqueue(operation)

    entity_key = "tenant-1:issue:issue-1"
    service._entity_versions[entity_key] = "v2"

    service.sync(make_sync_request())

    result = service.resolve_conflict(
        ConflictResolutionRequest(
            tenant_id="tenant-1",
            operation_id="op-retry",
            resolution="retry_client",
            actor_id="user-1",
            expected_server_version="v1",
        )
    )

    assert result.status == SyncStatus.PENDING


def test_accept_server_rejects_client_operation():
    service = OfflineSyncService()

    operation = make_operation(
        operation_id="op-server",
        entity_id="issue-1",
        payload={
            "status": "Resolved",
            "expected_server_version": "v1",
        },
    )

    service.enqueue(operation)

    entity_key = "tenant-1:issue:issue-1"
    service._entity_versions[entity_key] = "v2"

    service.sync(make_sync_request())

    result = service.resolve_conflict(
        ConflictResolutionRequest(
            tenant_id="tenant-1",
            operation_id="op-server",
            resolution="accept_server",
            actor_id="user-1",
        )
    )

    assert result.status == SyncStatus.REJECTED
    assert result.conflict_reason == "server_version_retained"


def test_scope_revocation_purges_pending_operations():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            operation_id="op-purge",
            scope_version="v1",
        )
    )

    result = service.revoke_scope(
        ScopeRevocationRequest(
            tenant_id="tenant-1",
            actor_id="admin-1",
            revoked_scope_version="v1",
        )
    )

    assert result.purged == 1
    assert result.pending == 0

    stored = service.get_operation(
        tenant_id="tenant-1",
        operation_id="op-purge",
    )

    assert stored.status == SyncStatus.PURGED


def test_revoked_scope_rejects_new_operation():
    service = OfflineSyncService()

    service.revoke_scope(
        ScopeRevocationRequest(
            tenant_id="tenant-1",
            actor_id="admin-1",
            revoked_scope_version="v1",
        )
    )

    result = service.enqueue(
        make_operation(
            operation_id="op-revoked",
            scope_version="v1",
        )
    )

    assert result.status == SyncStatus.REJECTED
    assert result.conflict_reason == "scope_version_revoked"


def test_revoked_sync_scope_does_not_process_queue():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            operation_id="op-revoked-sync",
            scope_version="v1",
        )
    )

    service.revoke_scope(
        ScopeRevocationRequest(
            tenant_id="tenant-1",
            actor_id="admin-1",
            revoked_scope_version="v1",
        )
    )

    result = service.sync(make_sync_request())

    assert result.accepted_count == 0
    assert result.operations == []


def test_cross_tenant_operation_access_is_blocked():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            tenant_id="tenant-1",
            operation_id="op-tenant",
        )
    )

    with pytest.raises(PermissionError):
        service.get_operation(
            tenant_id="tenant-2",
            operation_id="op-tenant",
        )


def test_evidence_and_attestation_are_stored():
    service = OfflineSyncService()

    operation = make_operation(
        operation_id="op-evidence",
    )

    operation.evidence_reference = "evidence-123"
    operation.attestation = "device=device-1;signature=valid"

    service.enqueue(operation)

    stored = service._operations["op-evidence"]

    assert stored["evidence_reference"] == "evidence-123"
    assert stored["attestation"] == (
        "device=device-1;signature=valid"
    )


def test_queue_stats():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            operation_id="op-stats",
        )
    )

    stats = service.queue_stats(
        tenant_id="tenant-1"
    )

    assert stats.pending == 1
    assert stats.accepted == 0
    assert stats.rejected == 0
    assert stats.conflicts == 0
    assert stats.purged == 0


def test_operation_get_preserves_status():
    service = OfflineSyncService()

    service.enqueue(
        make_operation(
            operation_id="op-get",
        )
    )

    result = service.get_operation(
        tenant_id="tenant-1",
        operation_id="op-get",
    )

    assert result.operation_id == "op-get"
    assert result.tenant_id == "tenant-1"
    assert result.status == SyncStatus.PENDING