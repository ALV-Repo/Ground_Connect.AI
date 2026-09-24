from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.vendor import VendorElevationRequest
from app.services.vendor import vendor_elevation_service


router = APIRouter(
    prefix="/vendor",
    tags=["Vendor Support"],
)


# ============================================================
# BE-010: Vendor Support Elevation
# ============================================================


@router.post("/elevation")
def request_elevation(
    request: VendorElevationRequest,
):
    """
    Request temporary vendor support elevation.
    """
    try:
        return vendor_elevation_service.request_elevation(
            vendor_id=request.vendor_id,
            tenant_id=request.tenant_id,
            requested_by=request.requested_by,
            reason=request.reason,
            duration_minutes=request.duration_minutes,
            scopes=request.scopes,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/elevation/{elevation_id}")
def get_elevation(
    elevation_id: str,
    tenant_id: str = Query(...),
):
    """
    Get vendor elevation details.
    """
    try:
        return vendor_elevation_service.get_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.post("/elevation/{elevation_id}/approve")
def approve_elevation(
    elevation_id: str,
    tenant_id: str = Query(...),
    approved_by: str = Query(...),
):
    """
    Approve a pending vendor elevation request.
    """
    try:
        return vendor_elevation_service.approve_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
            approved_by=approved_by,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/elevation/{elevation_id}/reject")
def reject_elevation(
    elevation_id: str,
    tenant_id: str = Query(...),
    rejected_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    """
    Reject a pending vendor elevation request.
    """
    try:
        return vendor_elevation_service.reject_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
            rejected_by=rejected_by,
            reason=reason,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/elevation/{elevation_id}/revoke")
def revoke_elevation(
    elevation_id: str,
    tenant_id: str = Query(...),
    revoked_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    """
    Revoke an active or pending vendor elevation.
    """
    try:
        return vendor_elevation_service.revoke_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
            revoked_by=revoked_by,
            reason=reason,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/elevation/{elevation_id}/active")
def check_active_elevation(
    elevation_id: str,
    tenant_id: str = Query(...),
):
    """
    Check whether a vendor elevation is currently active.
    """
    try:
        active = vendor_elevation_service.is_active(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
        )

        return {
            "elevation_id": elevation_id,
            "active": active,
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.get("/elevations")
def list_elevations(
    tenant_id: str = Query(...),
    vendor_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List vendor elevation requests for a tenant.
    """
    try:
        return {
            "items": vendor_elevation_service.list_elevations(
                tenant_id=tenant_id,
                vendor_id=vendor_id,
                status=status,
                limit=limit,
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/elevations/cleanup")
def cleanup_expired_elevations():
    """
    Mark expired vendor elevations as expired.
    """
    return vendor_elevation_service.cleanup_expired()


@router.get("/statistics")
def vendor_statistics(
    tenant_id: str = Query(...),
):
    """
    Return vendor elevation statistics.
    """
    try:
        return vendor_elevation_service.statistics(
            tenant_id=tenant_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc