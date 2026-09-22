from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# BE-014 — Notification Delivery
# ============================================================

class NotificationRecipient(BaseModel):
    recipient_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    channel: str = Field(
        default="in_app",
        max_length=32,
    )

    endpoint: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        allowed = {
            "in_app",
            "push",
            "sms",
            "email",
            "webhook",
        }

        if value not in allowed:
            raise ValueError(
                f"channel must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class NotificationCreateRequest(BaseModel):
    notification_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=300,
    )

    body: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    created_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    recipients: List[NotificationRecipient] = Field(
        ...,
        min_length=1,
        max_length=200000,
    )

    priority: str = Field(
        default="normal",
        max_length=32,
    )

    scheduled_at: Optional[datetime] = None

    expires_at: Optional[datetime] = None

    metadata: dict = Field(
        default_factory=dict,
    )

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


class NotificationResponse(BaseModel):
    notification_id: str

    tenant_id: str

    title: str
    body: str

    created_by: str

    recipients: List[NotificationRecipient]

    priority: str

    status: str

    created_at: datetime
    updated_at: datetime

    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    delivered_count: int = 0
    failed_count: int = 0
    pending_count: int = 0

    metadata: dict = Field(
        default_factory=dict,
    )


class NotificationDeliveryRequest(BaseModel):
    notification_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    recipient_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    channel: str = Field(
        default="in_app",
        max_length=32,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        allowed = {
            "in_app",
            "push",
            "sms",
            "email",
            "webhook",
        }

        if value not in allowed:
            raise ValueError(
                f"channel must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class NotificationDeliveryResponse(BaseModel):
    success: bool

    notification_id: str
    recipient_id: str

    channel: str

    status: str

    delivered_at: Optional[datetime] = None

    error: Optional[str] = None


class NotificationRetryRequest(BaseModel):
    notification_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    recipient_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class NotificationRetryResponse(BaseModel):
    success: bool

    notification_id: str

    retried_count: int

    status: str


class NotificationCancelRequest(BaseModel):
    notification_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class NotificationCancelResponse(BaseModel):
    success: bool

    notification_id: str

    cancelled: bool

    cancelled_by: str

    cancelled_at: datetime


class NotificationStatusResponse(BaseModel):
    notification_id: str

    status: str

    total_recipients: int

    delivered_count: int
    failed_count: int
    pending_count: int

    retry_count: int = 0

    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]

    total: int

    page: int = 1
    page_size: int = 50


class NotificationSearchRequest(BaseModel):
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    query: Optional[str] = Field(
        default=None,
        max_length=300,
    )

    status: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    channel: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    priority: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    page: int = Field(
        default=1,
        ge=1,
    )

    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
    )


# ============================================================
# BE-017 — Observability / Metrics
# ============================================================

class MetricRecord(BaseModel):
    metric_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    value: float

    timestamp: datetime

    labels: Dict[str, str] = Field(
        default_factory=dict,
    )


class MetricSnapshotResponse(BaseModel):
    metrics: Dict[str, float]

    generated_at: datetime


class TraceContextResponse(BaseModel):
    correlation_id: str
    trace_id: str
    span_id: str

    created_at: datetime


class ObservabilityEventRequest(BaseModel):
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    correlation_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    trace_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    actor_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    tenant_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    metadata: dict = Field(
        default_factory=dict,
    )


class ObservabilityEventResponse(BaseModel):
    success: bool

    event_id: str

    event_type: str

    correlation_id: str

    trace_id: str

    timestamp: datetime


class SIEMStatusResponse(BaseModel):
    enabled: bool

    endpoint_configured: bool

    forwarding_ready: bool

    forwarded_events: int = 0

    failed_events: int = 0


class ObservabilityHealthResponse(BaseModel):
    metrics_enabled: bool

    tracing_enabled: bool

    siem_enabled: bool

    correlation_header: str

    active_trace_contexts: int

    generated_at: datetime


# ============================================================
# Common responses
# ============================================================

class NotificationSuccessResponse(BaseModel):
    success: bool = True

    message: str = "Notification operation completed successfully."


class NotificationErrorResponse(BaseModel):
    success: bool = False

    error: str