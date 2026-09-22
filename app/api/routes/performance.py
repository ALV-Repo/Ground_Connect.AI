from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.performance import performance_service


router = APIRouter(
    prefix="/performance",
    tags=["Performance"],
)


# ============================================================
# BE-015: Performance Metrics
# ============================================================


@router.post("/operations")
def record_operation(
    payload: Dict[str, Any],
):
    """
    Record execution information for an operation.
    """
    try:
        return performance_service.record_operation(
            operation=payload.get("operation"),
            duration_ms=payload.get("duration_ms"),
            success=payload.get("success", True),
            endpoint=payload.get("endpoint"),
            tenant_id=payload.get("tenant_id"),
            status_code=payload.get("status_code"),
            correlation_id=payload.get("correlation_id"),
            metadata=payload.get("metadata"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Metrics
# ============================================================


@router.get("/metrics")
def performance_metrics(
    operation: Optional[str] = Query(None),
):
    """
    Return aggregated performance metrics.
    """
    try:
        return performance_service.get_operation_metrics(
            operation=operation,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/summary")
def performance_summary():
    """
    Return a performance summary.
    """
    try:
        return performance_service.get_summary()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# Slow Operations
# ============================================================


@router.get("/slow-operations")
def slow_operations(
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
):
    """
    Return operations exceeding the configured
    performance threshold.
    """
    try:
        return {
            "items": performance_service.list_slow_operations(
                limit=limit,
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Recent Operations
# ============================================================


@router.get("/operations/recent")
def recent_operations(
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
    operation: Optional[str] = Query(None),
):
    """
    Return recently recorded operations.
    """
    try:
        return {
            "items": performance_service.get_recent_operations(
                limit=limit,
                operation=operation,
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Request Timeout
# ============================================================


@router.get("/timeout")
def timeout_configuration(
    duration_ms: Optional[float] = Query(
        None,
        ge=0,
    ),
):
    """
    Return request timeout information.

    If duration_ms is supplied, the endpoint also evaluates
    whether that duration exceeds the configured timeout.
    """
    try:
        if duration_ms is None:
            return {
                "timeout_seconds": getattr(
                    __import__(
                        "app.core.config",
                        fromlist=["settings"],
                    ),
                    "settings",
                ).request_timeout_seconds
            }

        return performance_service.check_request_timeout(
            duration_ms=duration_ms,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# Load Control
# ============================================================


@router.post("/load-control")
def load_control(
    payload: Dict[str, Any],
):
    """
    Evaluate whether the system can accept additional load.
    """
    try:
        return performance_service.load_control(
            active_requests=payload.get("active_requests", 0),
            max_concurrent_requests=payload.get(
                "max_concurrent_requests",
                100,
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Reset Metrics
# ============================================================


@router.post("/reset")
def reset_metrics():
    """
    Reset in-memory performance metrics.
    """
    try:
        return performance_service.reset_metrics()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc