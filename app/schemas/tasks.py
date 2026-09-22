from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# BE-009 — Task Engine & Evidence
# ============================================================

class TaskCreateRequest(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)

    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(
        default=None,
        max_length=10000,
    )

    created_by: str = Field(..., min_length=1, max_length=128)

    assignee_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    priority: str = Field(
        default="normal",
        max_length=32,
    )

    due_at: Optional[datetime] = None

    metadata: dict = Field(default_factory=dict)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        allowed = {
            "low",
            "normal",
            "high",
            "urgent",
        }

        if value not in allowed:
            raise ValueError(
                f"priority must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class TaskResponse(BaseModel):
    task_id: str
    tenant_id: str

    title: str
    description: Optional[str] = None

    created_by: str
    assignee_id: Optional[str] = None

    priority: str
    status: str

    due_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

    metadata: dict = Field(default_factory=dict)


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=300,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=10000,
    )

    assignee_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    priority: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    due_at: Optional[datetime] = None

    status: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    metadata: Optional[dict] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        allowed = {
            "low",
            "normal",
            "high",
            "urgent",
        }

        if value not in allowed:
            raise ValueError(
                f"priority must be one of: {', '.join(sorted(allowed))}"
            )

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        allowed = {
            "pending",
            "in_progress",
            "completed",
            "cancelled",
            "overdue",
        }

        if value not in allowed:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class TaskListResponse(BaseModel):
    items: List[TaskResponse]

    total: int

    page: int = 1
    page_size: int = 50


class TaskSearchRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)

    query: Optional[str] = Field(
        default=None,
        max_length=300,
    )

    assignee_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    status: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    priority: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


# ============================================================
# Evidence
# ============================================================

class EvidenceCreateRequest(BaseModel):
    evidence_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    task_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    uploaded_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    file_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    content_type: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    size_bytes: int = Field(
        ...,
        ge=0,
        le=25 * 1024 * 1024,
    )

    sha256: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    storage_reference: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    metadata: dict = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    evidence_id: str
    task_id: str

    uploaded_by: str

    file_name: str
    content_type: str
    size_bytes: int

    sha256: Optional[str] = None

    storage_reference: Optional[str] = None

    created_at: datetime

    verified: bool = False

    metadata: dict = Field(default_factory=dict)


class EvidenceVerificationRequest(BaseModel):
    evidence_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    expected_sha256: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    verified_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class EvidenceVerificationResponse(BaseModel):
    success: bool

    evidence_id: str

    verified: bool

    actual_sha256: Optional[str] = None
    expected_sha256: Optional[str] = None

    verified_by: str
    verified_at: datetime


class EvidenceListResponse(BaseModel):
    items: List[EvidenceResponse]

    total: int


# ============================================================
# BE-010 — Vendor Support Elevation
# ============================================================

class VendorElevationRequest(BaseModel):
    vendor_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )

    duration_minutes: int = Field(
        default=30,
        ge=1,
        le=60,
    )

    scope: List[str] = Field(
        default_factory=list,
        max_length=100,
    )


class VendorElevationResponse(BaseModel):
    success: bool

    elevation_id: str

    vendor_id: str
    tenant_id: str

    scope: List[str]

    status: str

    requested_by: str

    approved_by: Optional[str] = None

    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    reason: str


class VendorElevationApprovalRequest(BaseModel):
    elevation_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    approved_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    approve: bool

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class VendorElevationRevokeRequest(BaseModel):
    elevation_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    revoked_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class VendorElevationRevokeResponse(BaseModel):
    success: bool

    elevation_id: str

    revoked: bool

    revoked_by: str
    revoked_at: datetime


# ============================================================
# BE-011 — Two-Person Integrity
# ============================================================

class TPIRequest(BaseModel):
    operation_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    operation_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    payload: dict = Field(
        default_factory=dict,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class TPIResponse(BaseModel):
    success: bool

    operation_id: str

    status: str

    requested_by: str

    approved_by: Optional[str] = None

    created_at: datetime
    approved_at: Optional[datetime] = None

    reason: Optional[str] = None


class TPIApprovalRequest(BaseModel):
    operation_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    approved_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    approve: bool

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class TPIApprovalResponse(BaseModel):
    success: bool

    operation_id: str

    status: str

    approved_by: str

    approved_at: Optional[datetime] = None

    reason: Optional[str] = None


class TPICheckResponse(BaseModel):
    operation_id: str

    requires_two_person_integrity: bool

    first_actor: Optional[str] = None
    second_actor: Optional[str] = None

    approved: bool

    status: str


# ============================================================
# Common Task Actions
# ============================================================

class TaskActionRequest(BaseModel):
    task_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    action: str = Field(
        ...,
        min_length=1,
        max_length=64,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        allowed = {
            "start",
            "complete",
            "cancel",
            "reopen",
            "assign",
            "unassign",
        }

        if value not in allowed:
            raise ValueError(
                f"action must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class TaskActionResponse(BaseModel):
    success: bool

    task_id: str

    action: str

    status: str

    updated_at: datetime


# ============================================================
# Generic success/error responses
# ============================================================

class TaskSuccessResponse(BaseModel):
    success: bool = True
    message: str = "Operation completed successfully."


class TaskErrorResponse(BaseModel):
    success: bool = False
    error: str