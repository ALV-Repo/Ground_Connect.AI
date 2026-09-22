from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MessageRecipient(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    branch_id: Optional[str] = Field(default=None, max_length=128)


class MessageCreateRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)

    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=50000)

    created_by: str = Field(..., min_length=1, max_length=128)

    recipients: List[MessageRecipient] = Field(
        ...,
        min_length=1,
        max_length=200000,
    )

    priority: str = Field(default="normal", max_length=32)
    expires_at: Optional[datetime] = None

    metadata: dict = Field(default_factory=dict)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        allowed = {"low", "normal", "high", "urgent"}

        if value not in allowed:
            raise ValueError(
                f"priority must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class MessageResponse(BaseModel):
    message_id: str
    tenant_id: str

    subject: str
    body: str

    created_by: str
    recipients: List[MessageRecipient]

    priority: str

    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    delivered_count: int = 0
    failed_count: int = 0

    metadata: dict = Field(default_factory=dict)


class MessageStatusResponse(BaseModel):
    message_id: str
    status: str

    total_recipients: int
    delivered_count: int
    failed_count: int
    pending_count: int

    created_at: datetime
    updated_at: datetime


class PropagationRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128)

    stage: str = Field(default="initial", max_length=32)
    batch_size: int = Field(default=1000, ge=1, le=200000)

    requested_by: str = Field(..., min_length=1, max_length=128)


class PropagationResponse(BaseModel):
    success: bool
    message_id: str

    stage: str
    status: str

    total_recipients: int
    processed: int
    delivered: int
    failed: int

    started_at: datetime
    completed_at: Optional[datetime] = None


class BlastRadiusRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)

    recipient_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=200000,
    )

    requested_by: str = Field(..., min_length=1, max_length=128)

    max_recipients: int = Field(
        default=200000,
        ge=1,
        le=200000,
    )


class BlastRadiusResponse(BaseModel):
    success: bool

    tenant_id: str

    requested_count: int
    allowed_count: int
    blocked_count: int

    affected_members: List[str] = Field(default_factory=list)
    blocked_members: List[str] = Field(default_factory=list)

    reason: Optional[str] = None


class StagedDeliveryRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128)

    stage_name: str = Field(..., min_length=1, max_length=64)

    batch_size: int = Field(
        default=1000,
        ge=1,
        le=200000,
    )

    delay_seconds: int = Field(
        default=0,
        ge=0,
        le=86400,
    )

    requested_by: str = Field(..., min_length=1, max_length=128)


class StagedDeliveryResponse(BaseModel):
    success: bool
    message_id: str
    stage_name: str

    batch_size: int
    total_batches: int
    current_batch: int

    status: str

    started_at: datetime
    updated_at: datetime


class DeliveryHaltRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128)

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )

    requested_by: str = Field(..., min_length=1, max_length=128)


class DeliveryHaltResponse(BaseModel):
    success: bool

    message_id: str
    halted: bool

    reason: str
    halted_by: str
    halted_at: datetime


class MessagePropagationEvent(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=128)

    message_id: str = Field(..., min_length=1, max_length=128)

    recipient_id: str = Field(..., min_length=1, max_length=128)

    tenant_id: str = Field(..., min_length=1, max_length=128)

    event_type: str = Field(..., min_length=1, max_length=64)

    timestamp: datetime

    success: bool
    error: Optional[str] = None


class MessageSearchRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)

    query: Optional[str] = Field(
        default=None,
        max_length=300,
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


class MessageListResponse(BaseModel):
    items: List[MessageResponse]

    total: int

    page: int
    page_size: int


class MessageCancelRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128)

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    requested_by: str = Field(..., min_length=1, max_length=128)


class MessageCancelResponse(BaseModel):
    success: bool

    message_id: str
    cancelled: bool

    cancelled_by: str
    cancelled_at: datetime