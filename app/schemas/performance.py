from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PerformanceOperationRequest(BaseModel):
    operation: str = Field(
        min_length=1,
        max_length=255,
    )
    duration_ms: float = Field(
        ge=0,
    )
    success: bool = True
    endpoint: str | None = None
    tenant_id: str | None = None
    status_code: int | None = Field(
        default=None,
        ge=100,
        le=599,
    )
    correlation_id: str | None = None
    metadata: dict[str, Any] | None = None


class LoadControlRequest(BaseModel):
    active_requests: int = Field(
        default=0,
        ge=0,
    )
    max_concurrent_requests: int = Field(
        default=100,
        gt=0,
    )