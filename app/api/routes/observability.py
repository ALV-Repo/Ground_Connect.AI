from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.observability import observability_service
from app.schemas.observability import (
    MetricIncrementRequest,
    ObservabilityEventRequest,
    TimingMetricRequest,
    TraceContextRequest,
)


router = APIRouter(
    prefix="/observability",
    tags=["Observability & SIEM"],
)


# ============================================================
# BE-017: Observability & SIEM
# ============================================================


@router.post("/events")
def record_event(payload: ObservabilityEventRequest):
    """
    Record a structured observability event.
    """

    try:
        return observability_service.log_event(
            event=payload.event,
            level=payload.level,
            correlation_id=payload.correlation_id,
            subject_id=payload.subject_id,
            tenant_id=payload.tenant_id,
            request_id=payload.request_id,
            trace_id=payload.trace_id,
            duration_ms=payload.duration_ms,
            status_code=payload.status_code,
            metadata=payload.metadata,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/correlation-id")
def get_correlation_id():
    """
    Generate a correlation/trace context.
    """

    try:
        context = observability_service.create_trace_context()

        return {
            "correlation_id": context["correlation_id"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get("/metrics")
def get_metrics():
    """
    Return current application metrics.
    """

    try:
        return observability_service.metrics_snapshot()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.post("/metrics/increment")
def increment_metric(payload: MetricIncrementRequest):
    """
    Increment an application counter.
    """

    try:
        return observability_service.increment_counter(
            name=payload.name,
            value=payload.value,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/metrics/timing")
def record_timing(payload: TimingMetricRequest):
    """
    Record timing information for an operation.
    """

    try:
        return observability_service.record_timing(
            name=payload.name,
            duration_ms=payload.duration_ms,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/traces")
def create_trace(payload: TraceContextRequest | None = None):
    """
    Create correlation/trace/span context.
    """

    try:
        return observability_service.create_trace_context(
            correlation_id=(
                payload.correlation_id
                if payload is not None
                else None
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/events/recent")
def recent_events(
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
):
    """
    Return recent structured observability events.
    """

    try:
        return {
            "items": observability_service.recent_events(
                limit=limit,
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/siem/status")
def siem_status():
    """
    Return SIEM configuration/readiness information.
    """

    return {
        "enabled": observability_service.siem_enabled,
        "endpoint_configured": bool(
            observability_service.siem_endpoint
        ),
        "forwarding_implementation": "readiness_stub",
    }


@router.post("/siem/forward")
def forward_to_siem():
    """
    Forwarding readiness endpoint.

    Actual outbound SIEM transport is intentionally not
    implemented in the current core service.
    """

    return {
        "accepted": False,
        "forwarded": False,
        "reason": (
            "SIEM forwarding is currently a readiness stub "
            "in ObservabilityService."
        ),
        "siem_enabled": observability_service.siem_enabled,
        "endpoint_configured": bool(
            observability_service.siem_endpoint
        ),
    }


@router.get("/status")
def observability_status():
    """
    Return observability subsystem status.
    """

    metrics = observability_service.metrics_snapshot()

    return {
        "status": "ready",
        "service": observability_service.service_name,
        "environment": observability_service.environment,
        "siem_enabled": observability_service.siem_enabled,
        "siem_endpoint_configured": bool(
            observability_service.siem_endpoint
        ),
        "metrics": metrics,
    }