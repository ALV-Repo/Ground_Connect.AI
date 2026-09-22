from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.schemas.offline import (
    ConflictResolutionRequest,
    OfflineOperationRequest,
    OfflineOperationResponse,
    OfflineQueueStatsResponse,
    ScopeRevocationRequest,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncStatus,
)


class OfflineSyncService:
    """
    BE-021 Offline Sync Engine.

    Guarantees:
    - Ordered queue per tenant.
    - Idempotent operation ingestion.
    - Resumable batch processing.
    - Explicit conflict state.
    - No silent overwrite.
    - Scope-version based purge.
    - Offline evidence / attestation retention.
    """

    def __init__(self) -> None:
        self._queues: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._operations: Dict[str, Dict[str, Any]] = {}
        self._idempotency: Dict[str, str] = {}
        self._entity_versions: Dict[str, str] = {}
        self._sequence: Dict[str, int] = defaultdict(int)
        self._revoked_scopes: Dict[str, set[str]] = defaultdict(set)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _entity_key(
        tenant_id: str,
        entity_type: str,
        entity_id: str,
    ) -> str:
        return f"{tenant_id}:{entity_type}:{entity_id}"

    def enqueue(
        self,
        request: OfflineOperationRequest,
    ) -> OfflineOperationResponse:
        """
        Add an offline operation to the durable logical queue.

        Duplicate idempotency keys return the original operation rather
        than creating a second mutation.
        """

        existing_operation_id = self._idempotency.get(
            request.idempotency_key
        )

        if existing_operation_id:
            existing = self._operations[existing_operation_id]
            return self._response(existing)

        if request.scope_version in self._revoked_scopes[
            request.tenant_id
        ]:
            operation = self._create_operation(
                request=request,
                status=SyncStatus.REJECTED,
                conflict_reason="scope_version_revoked",
            )

            self._operations[request.operation_id] = operation
            self._idempotency[request.idempotency_key] = (
                request.operation_id
            )

            return self._response(operation)

        self._sequence[request.tenant_id] += 1

        operation = self._create_operation(
            request=request,
            status=SyncStatus.PENDING,
        )

        operation["sequence_number"] = self._sequence[
            request.tenant_id
        ]

        self._operations[request.operation_id] = operation
        self._idempotency[request.idempotency_key] = (
            request.operation_id
        )

        self._queues[request.tenant_id].append(
            request.operation_id
        )

        return self._response(operation)

    def _create_operation(
        self,
        *,
        request: OfflineOperationRequest,
        status: SyncStatus,
        conflict_reason: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "operation_id": request.operation_id,
            "tenant_id": request.tenant_id,
            "actor_id": request.actor_id,
            "entity_type": request.entity_type,
            "entity_id": request.entity_id,
            "operation": request.operation,
            "payload": dict(request.payload),
            "client_timestamp": request.client_timestamp,
            "idempotency_key": request.idempotency_key,
            "scope_version": request.scope_version,
            "evidence_reference": request.evidence_reference,
            "attestation": request.attestation,
            "status": status,
            "sequence_number": 0,
            "accepted_at": None,
            "conflict_reason": conflict_reason,
            "server_version": None,
        }

    def sync(
        self,
        request: SyncBatchRequest,
    ) -> SyncBatchResponse:
        """
        Process queued operations in sequence order.

        The operation is accepted only when the entity version has
        not changed since the client operation was prepared.
        """

        if request.scope_version in self._revoked_scopes[
            request.tenant_id
        ]:
            return SyncBatchResponse(
                tenant_id=request.tenant_id,
                accepted_count=0,
                pending_count=self._count(
                    request.tenant_id,
                    SyncStatus.PENDING,
                ),
                conflict_count=0,
                rejected_count=0,
                operations=[],
            )

        queue = self._queues[request.tenant_id]

        processed: List[OfflineOperationResponse] = []

        for operation_id in list(queue):
            if len(processed) >= request.max_operations:
                break

            operation = self._operations[operation_id]

            if operation["status"] != SyncStatus.PENDING:
                continue

            if operation["scope_version"] in self._revoked_scopes[
                request.tenant_id
            ]:
                operation["status"] = SyncStatus.REJECTED
                operation["conflict_reason"] = (
                    "scope_version_revoked"
                )
                processed.append(self._response(operation))
                continue

            entity_key = self._entity_key(
                operation["tenant_id"],
                operation["entity_type"],
                operation["entity_id"],
            )

            current_version = self._entity_versions.get(
                entity_key
            )

            expected_version = operation["payload"].get(
                "expected_server_version"
            )

            if (
                expected_version is not None
                and current_version is not None
                and expected_version != current_version
            ):
                operation["status"] = SyncStatus.CONFLICT
                operation["conflict_reason"] = (
                    "server_version_changed"
                )
                processed.append(self._response(operation))
                continue

            new_version = (
                f"v{operation['sequence_number']}"
            )

            self._entity_versions[entity_key] = new_version

            operation["status"] = SyncStatus.ACCEPTED
            operation["accepted_at"] = self._now()
            operation["server_version"] = new_version

            processed.append(self._response(operation))

        accepted_count = sum(
            item.status == SyncStatus.ACCEPTED
            for item in processed
        )

        conflict_count = sum(
            item.status == SyncStatus.CONFLICT
            for item in processed
        )

        rejected_count = sum(
            item.status == SyncStatus.REJECTED
            for item in processed
        )

        pending_count = self._count(
            request.tenant_id,
            SyncStatus.PENDING,
        )

        return SyncBatchResponse(
            tenant_id=request.tenant_id,
            accepted_count=accepted_count,
            pending_count=pending_count,
            conflict_count=conflict_count,
            rejected_count=rejected_count,
            operations=processed,
        )

    def resolve_conflict(
        self,
        request: ConflictResolutionRequest,
    ) -> OfflineOperationResponse:
        operation = self._operations.get(
            request.operation_id
        )

        if operation is None:
            raise KeyError("Offline operation not found")

        self._tenant_check(
            operation,
            request.tenant_id,
        )

        if operation["status"] != SyncStatus.CONFLICT:
            raise ValueError(
                "Operation is not in conflict state"
            )

        if request.resolution == "accept_server":
            operation["status"] = SyncStatus.REJECTED
            operation["conflict_reason"] = (
                "server_version_retained"
            )

        elif request.resolution == "retry_client":
            if (
                request.expected_server_version is not None
                and operation["payload"].get(
                    "expected_server_version"
                )
                != request.expected_server_version
            ):
                raise ValueError(
                    "Expected server version does not match "
                    "the original operation"
                )

            operation["status"] = SyncStatus.PENDING
            operation["conflict_reason"] = None

        else:
            raise ValueError(
                "resolution must be accept_server or retry_client"
            )

        return self._response(operation)

    def revoke_scope(
        self,
        request: ScopeRevocationRequest,
    ) -> OfflineQueueStatsResponse:
        self._revoked_scopes[
            request.tenant_id
        ].add(request.revoked_scope_version)

        purged = 0

        for operation in self._operations.values():
            if operation["tenant_id"] != request.tenant_id:
                continue

            if (
                operation["scope_version"]
                == request.revoked_scope_version
                and operation["status"]
                in {
                    SyncStatus.PENDING,
                    SyncStatus.CONFLICT,
                }
            ):
                operation["status"] = SyncStatus.PURGED
                operation["conflict_reason"] = (
                    "scope_revoked"
                )
                purged += 1

        return self.queue_stats(
            tenant_id=request.tenant_id,
        )

    def queue_stats(
        self,
        *,
        tenant_id: str,
    ) -> OfflineQueueStatsResponse:
        return OfflineQueueStatsResponse(
            tenant_id=tenant_id,
            pending=self._count(
                tenant_id,
                SyncStatus.PENDING,
            ),
            accepted=self._count(
                tenant_id,
                SyncStatus.ACCEPTED,
            ),
            rejected=self._count(
                tenant_id,
                SyncStatus.REJECTED,
            ),
            conflicts=self._count(
                tenant_id,
                SyncStatus.CONFLICT,
            ),
            purged=self._count(
                tenant_id,
                SyncStatus.PURGED,
            ),
        )

    def get_operation(
        self,
        *,
        tenant_id: str,
        operation_id: str,
    ) -> OfflineOperationResponse:
        operation = self._operations.get(operation_id)

        if operation is None:
            raise KeyError("Offline operation not found")

        self._tenant_check(
            operation,
            tenant_id,
        )

        return self._response(operation)

    def _count(
        self,
        tenant_id: str,
        status: SyncStatus,
    ) -> int:
        return sum(
            1
            for operation in self._operations.values()
            if operation["tenant_id"] == tenant_id
            and operation["status"] == status
        )

    @staticmethod
    def _tenant_check(
        operation: Dict[str, Any],
        tenant_id: str,
    ) -> None:
        if operation["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant offline operation access denied"
            )

    @staticmethod
    def _response(
        operation: Dict[str, Any],
    ) -> OfflineOperationResponse:
        return OfflineOperationResponse(
            operation_id=operation["operation_id"],
            tenant_id=operation["tenant_id"],
            status=operation["status"],
            sequence_number=operation["sequence_number"],
            accepted_at=operation["accepted_at"],
            conflict_reason=operation["conflict_reason"],
            server_version=operation["server_version"],
        )


offline_sync_service = OfflineSyncService()