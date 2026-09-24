from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.tpi import tpi_service
from app.schemas.tpi import TPICreateOperationRequest

router = APIRouter(
    prefix="/tpi",
    tags=["Two-Person Integrity"],
)


# ============================================================
# Create TPI Operation
# ============================================================

@router.post("/operations")
def create_operation(
    request: TPICreateOperationRequest,
):
    try:
        return tpi_service.create_operation(
            operation_id=request.operation_id,
            tenant_id=request.tenant_id,
            requested_by=request.requested_by,
            operation_type=request.operation_type,
            payload=request.payload,
            reason=request.reason,
            approval_window_seconds=request.approval_window_seconds,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Get Operation
# ============================================================

@router.get("/operations/{operation_id}")
def get_operation(
    operation_id: str,
    tenant_id: str = Query(...),
):
    operation = tpi_service.get_operation(
        operation_id=operation_id,
        tenant_id=tenant_id,
    )

    if operation is None:
        raise HTTPException(
            status_code=404,
            detail="TPI operation not found",
        )

    return operation


# ============================================================
# Approve Operation
# ============================================================

@router.post("/operations/{operation_id}/approve")
def approve_operation(
    operation_id: str,
    tenant_id: str = Query(...),
    approved_by: str = Query(...),
    approver_role: str = Query(...),
    mfa_otp: str = Query(...),
    reason: Optional[str] = Query(None),
):
    try:
        return tpi_service.approve_operation(
            operation_id=operation_id,
            tenant_id=tenant_id,
            approved_by=approved_by,
            approve=True,
            reason=reason,
            approver_role=approver_role,
            mfa_otp=mfa_otp,
            mfa_source="tpi",
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# Reject Operation
# ============================================================

@router.post("/operations/{operation_id}/reject")
def reject_operation(
    operation_id: str,
    tenant_id: str = Query(...),
    rejected_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    try:
        return tpi_service.approve_operation(
            operation_id=operation_id,
            tenant_id=tenant_id,
            approved_by=rejected_by,
            approve=False,
            reason=reason,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# Check Operation
# ============================================================

@router.get("/operations/{operation_id}/check")
def check_operation(
    operation_id: str,
    tenant_id: str = Query(...),
):
    try:
        return tpi_service.check_operation(
            operation_id=operation_id,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )


# ============================================================
# Require Approval
# ============================================================

@router.post("/operations/{operation_id}/require-approval")
def require_approval(
    operation_id: str,
    tenant_id: str = Query(...),
):
    try:
        return tpi_service.require_approval(
            operation_id=operation_id,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )


# ============================================================
# Cancel Operation
# ============================================================

@router.post("/operations/{operation_id}/cancel")
def cancel_operation(
    operation_id: str,
    tenant_id: str = Query(...),
    cancelled_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    try:
        return tpi_service.cancel_operation(
            operation_id=operation_id,
            tenant_id=tenant_id,
            cancelled_by=cancelled_by,
            reason=reason,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# BREAK-GLASS
# ============================================================

@router.post("/operations/{operation_id}/break-glass")
def break_glass_operation(
    operation_id: str,
    tenant_id: str = Query(...),
    break_glass_by: str = Query(...),
    reason: str = Query(...),
    operation_type: Optional[str] = Query("emergency"),
):
    """
    Emergency break-glass path.

    Requires:
    - actor identity
    - tenant
    - mandatory reason

    Generates:
    - break-glass event
    - Compliance notification
    - Security Administrator notification
    """

    try:
        return tpi_service.break_glass_operation(
            operation_id=operation_id,
            tenant_id=tenant_id,
            break_glass_by=break_glass_by,
            reason=reason,
            operation_type=operation_type,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# Break-Glass Event History
# ============================================================

@router.get("/break-glass/events")
def list_break_glass_events(
    tenant_id: str = Query(...),
):
    """
    Return break-glass events for the tenant.
    """

    return tpi_service.list_break_glass_events(
        tenant_id=tenant_id,
    )


# ============================================================
# List Operations
# ============================================================

@router.get("/operations")
def list_operations(
    tenant_id: str = Query(...),
    status: Optional[str] = Query(None),
):
    return tpi_service.list_operations(
        tenant_id=tenant_id,
        status=status,
    )


# ============================================================
# Statistics
# ============================================================

@router.get("/statistics")
def statistics(
    tenant_id: Optional[str] = Query(None),
):
    return tpi_service.statistics(
        tenant_id=tenant_id,
    )