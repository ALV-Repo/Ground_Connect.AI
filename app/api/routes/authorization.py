from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.authorization import (
    ADRQueryRequest,
    AuthorizationRequest,
    DenialQueryRequest,
    FieldAuthorizationRequest,
    GrantRequest,
    IdentityRegisterRequest,
    WhatCanAccessRequest,
    WhoCanAccessRequest,
)
from app.services.authorization import authorization_service


router = APIRouter(
    prefix="/authorization",
    tags=["Authorization"],
)


# ============================================================
# BE-003: Identity Registration
# ============================================================

@router.post("/identities")
def register_identity(
    request: IdentityRegisterRequest,
):
    try:
        result = authorization_service.register_identity(
            identity_id=request.subject_id,
            tenant_id=request.tenant_id,
            role=request.role,
            branch_id=request.branch_id,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/identities/{subject_id}")
def get_identity(
    subject_id: str,
):
    try:
        result = authorization_service.get_identity(
            subject_id=subject_id,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Identity not found",
            )

        return result

    except HTTPException:
        raise

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# ============================================================
# BE-003: Grants
# ============================================================

@router.post("/grants")
def add_grant(
    request: GrantRequest,
):
    try:
        return authorization_service.add_grant(
            subject_id=request.subject_id,
            tenant_id=request.tenant_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            branch_id=request.branch_id,
        )

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


@router.delete("/grants")
def revoke_grant(
    request: GrantRequest,
):
    try:
        return authorization_service.revoke_grant(
            subject_id=request.subject_id,
            tenant_id=request.tenant_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            branch_id=request.branch_id,
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
# BE-003: Authorization Check
# ============================================================

@router.post("/check")
def authorization_check(
    request: AuthorizationRequest,
):
    try:
        return authorization_service.authorize(
            subject_id=request.subject_id,
            tenant_id=request.tenant_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            branch_id=request.branch_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# BE-003: Access Query
# ============================================================

@router.get("/access")
def can_access(
    subject_id: str,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    branch_id: str | None = None,
):
    try:
        return authorization_service.can_access(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            branch_id=branch_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/decision")
def decision_details(
    request: AuthorizationRequest,
):
    try:
        return authorization_service.decision_details(
            subject_id=request.subject_id,
            tenant_id=request.tenant_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            branch_id=request.branch_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Cache
# ============================================================

@router.post("/cache/invalidate")
def invalidate_authorization_cache(
    subject_id: str | None = None,
):
    try:
        return authorization_service.invalidate_cache(
            subject_id=subject_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/cache/clear")
def clear_authorization_cache():
    try:
        return authorization_service.clear_cache()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to clear authorization cache",
        ) from exc