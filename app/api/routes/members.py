from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.members import member_service


router = APIRouter(
    prefix="/members",
    tags=["Members"],
)


# ============================================================
# BE-006: Member Lifecycle
# ============================================================


@router.post("")
def create_member(
    payload: Dict[str, Any],
):
    """
    Create a new member.
    """
    try:
        return member_service.create_member(
            member_id=payload.get("member_id"),
            tenant_id=payload.get("tenant_id"),
            name=payload.get("name"),
            role=payload.get("role", "member"),
            branch_id=payload.get("branch_id"),
            mobile=payload.get("mobile"),
            email=payload.get("email"),
            status=payload.get("status", "active"),
            metadata=payload.get("metadata"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.get("/{member_id}")
def get_member(
    member_id: str,
    tenant_id: str = Query(...),
):
    """
    Get a member by ID with tenant isolation.
    """
    try:
        member = member_service.get_member(
            member_id=member_id,
            tenant_id=tenant_id,
        )

        if member is None:
            raise HTTPException(
                status_code=404,
                detail="Member not found",
            )

        return member

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.patch("/{member_id}")
def update_member(
    member_id: str,
    tenant_id: str = Query(...),
    payload: Dict[str, Any] = None,
):
    """
    Update member information.
    """
    payload = payload or {}

    try:
        return member_service.update_member(
            member_id=member_id,
            tenant_id=tenant_id,
            name=payload.get("name"),
            mobile=payload.get("mobile"),
            email=payload.get("email"),
            role=payload.get("role"),
            status=payload.get("status"),
            branch_id=payload.get("branch_id"),
            metadata=payload.get("metadata"),
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


# ============================================================
# Member Lifecycle
# ============================================================


@router.post("/{member_id}/lifecycle")
def change_member_lifecycle(
    member_id: str,
    action: str = Query(...),
    tenant_id: str = Query(...),
    reason: Optional[str] = Query(None),
):
    """
    Change member lifecycle status.

    Supported actions:
    - activate
    - deactivate
    - suspend
    - restore
    """
    try:
        return member_service.lifecycle_action(
            member_id=member_id,
            tenant_id=tenant_id,
            action=action,
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


# ============================================================
# Delete Member
# ============================================================


@router.delete("/{member_id}")
def delete_member(
    member_id: str,
    tenant_id: str = Query(...),
    reason: Optional[str] = Query(None),
):
    """
    Delete a member from the service store.
    """
    try:
        deleted = member_service.delete_member(
            member_id=member_id,
            tenant_id=tenant_id,
            reason=reason,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Member not found",
            )

        return {
            "success": True,
            "member_id": member_id,
            "deleted": True,
        }

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# Search
# ============================================================


@router.get("")
def search_members(
    tenant_id: str = Query(...),
    query: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """
    Search members within a tenant.
    """
    try:
        return member_service.search_members(
            tenant_id=tenant_id,
            query=query,
            branch_id=branch_id,
            status=status,
            role=role,
            page=page,
            page_size=page_size,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Bulk Import
# ============================================================


@router.post("/bulk-import")
def bulk_import_members(
    tenant_id: str = Query(...),
    imported_by: str = Query(...),
    members: list[Dict[str, Any]] = [],
):
    """
    Bulk import members into a tenant.
    """
    try:
        result = member_service.bulk_import(
            tenant_id=tenant_id,
            records=members,
            source="api",
            dry_run=False,
        )

        return {
            "success": result["failed"] == 0,
            "result": result,
            "imported_by": imported_by,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# Statistics
# ============================================================


@router.get("/statistics/summary")
def member_statistics(
    tenant_id: str = Query(...),
):
    """
    Return member statistics for a tenant.
    """
    try:
        return member_service.statistics(
            tenant_id=tenant_id,
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc