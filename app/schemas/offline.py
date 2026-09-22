from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SyncStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICT = "conflict"
    PURGED = "purged"


class OfflineOperationRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    actor_id: str = Field(..., min_length=1, max_length=128)
    operation_id: str = Field(..., min_length=1, max_length=128)
    entity_type: str = Field(..., min_length=1, max_length=128)
    entity_id: str = Field(..., min_length=1, max_length=128)
    operation: str = Field(..., min_length=1, max_length=64)
    payload: Dict[str, Any] = Field(default_factory=dict)
    client_timestamp: datetime
    idempotency_key: str = Field(..., min_length=1, max_length=256)
    scope_version: str = Field(..., min_length=1, max_length=128)
    evidence_reference: Optional[str] = Field(
        default=None,
        max_length=1000,
    )
    attestation: Optional[str] = Field(
        default=None,
        max_length=2000,
    )


class OfflineOperationResponse(BaseModel):
    operation_id: str
    tenant_id: str
    status: SyncStatus
    sequence_number: int
    accepted_at: Optional[datetime] = None
    conflict_reason: Optional[str] = None
    server_version: Optional[str] = None


class SyncBatchRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    actor_id: str = Field(..., min_length=1, max_length=128)
    scope_version: str = Field(..., min_length=1, max_length=128)
    max_operations: int = Field(default=50, ge=1, le=500)


class SyncBatchResponse(BaseModel):
    tenant_id: str
    accepted_count: int
    pending_count: int
    conflict_count: int
    rejected_count: int
    operations: list[OfflineOperationResponse]


class ConflictResolutionRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    operation_id: str = Field(..., min_length=1, max_length=128)
    resolution: str = Field(..., min_length=1, max_length=64)
    actor_id: str = Field(..., min_length=1, max_length=128)
    expected_server_version: Optional[str] = Field(
        default=None,
        max_length=128,
    )


class ScopeRevocationRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    actor_id: str = Field(..., min_length=1, max_length=128)
    revoked_scope_version: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class OfflineQueueStatsResponse(BaseModel):
    tenant_id: str
    pending: int
    accepted: int
    rejected: int
    conflicts: int
    purged: int