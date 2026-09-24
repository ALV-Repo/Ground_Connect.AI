from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ObservabilityEventRequest(BaseModel):
    event: str = Field(
        default="application.event",
        min_length=1,
        max_length=255,
    )
    level: str = Field(
        default="INFO",
        min_length=1,
        max_length=20,
    )
    correlation_id: str | None = None
    subject_id: str | None = None
    tenant_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    status_code: int | None = Field(default=None, ge=100, le=599)
    metadata: dict[str, Any] | None = None


class MetricIncrementRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    value: int = Field(
        default=1,
        ge=0,
    )


class TimingMetricRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    duration_ms: float = Field(
        ge=0,
    )


class TraceContextRequest(BaseModel):
    correlation_id: str | None = None