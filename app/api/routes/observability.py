from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.observability import observability_service


router = APIRouter(
    prefix="/observability",
    tags=["Observability & SIEM"],
)


# ============================================================
# BE-017: Observability & SIEM
# ============================================================


@router.post("/events")
def record_event(payload: Dict[str, Any]):
    """
    Record a structured observability event.
    """

    try:
        return observability_service.log_event(
            event=payload.get(
                "event",
                payload.get("event_type", "application.event"),
            ),
            level=payload.get(
                "level",
                payload.get("severity", "INFO"),
            ),
            correlation_id=payload.get("correlation_id"),
            subject_id=payload.get("subject_id"),
            tenant_id=payload.get("tenant_id"),
            request_id=payload.get("request_id"),
            trace_id=payload.get("trace_id"),
            duration_ms=payload.get("duration_ms"),
            status_code=payload.get("status_code"),
            metadata=payload.get("metadata"),
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
def increment_metric(payload: Dict[str, Any]):
    """
    Increment an application counter.
    """

    try:
        name = payload.get("name")

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Metric name is required",
            )

        value = payload.get("value", 1)

        return observability_service.increment_counter(
            name=name,
            value=value,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/metrics/timing")
def record_timing(payload: Dict[str, Any]):
    """
    Record timing information for an operation.
    """

    try:
        name = payload.get("name")

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Timing metric name is required",
            )

        duration_ms = payload.get("duration_ms")

        if duration_ms is None:
            raise HTTPException(
                status_code=400,
                detail="duration_ms is required",
            )

        return observability_service.record_timing(
            name=name,
            duration_ms=duration_ms,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/traces")
def create_trace(payload: Optional[Dict[str, Any]] = None):
    """
    Create correlation/trace/span context.
    """

    try:
        payload = payload or {}

        return observability_service.create_trace_context(
            correlation_id=payload.get("correlation_id"),
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
def forward_to_siem(payload: Dict[str, Any]):
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