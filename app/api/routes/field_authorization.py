from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.authorization import (
    FieldAuthorizationRequest,
    FieldAuthorizationResponse,
    FieldPolicyRequest,
    FieldPolicyResponse,
    FieldCacheInvalidationRequest,
    FieldCacheInvalidationResponse,
)
from app.services.authorization import authorization_service


router = APIRouter(
    prefix="/field-authorization",
    tags=["Field Authorization"],
)


# ============================================================
# BE-005: Field-Level Authorization
# ============================================================


@router.post(
    "/check",
    response_model=FieldAuthorizationResponse,
)
def check_field_authorization(
    request: FieldAuthorizationRequest,
):
    """
    Check field-level access for a resource.
    """
    try:
        result = authorization_service.check_fields(
            subject_id=request.subject_id,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            tenant_id=request.tenant_id,
            branch_id=request.branch_id,
            fields=request.fields,
        )

        return result

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
# Field Policy
# ============================================================


@router.post(
    "/policies",
    response_model=FieldPolicyResponse,
)
def create_field_policy(
    request: FieldPolicyRequest,
):
    """
    Create a field-level authorization policy.
    """
    try:
        result = authorization_service.create_field_policy(
            role=request.role,
            resource_type=request.resource_type,
            field=request.field,
            actions=request.actions,
        )

        return result

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
# Field Cache Invalidation
# ============================================================


@router.post(
    "/cache/invalidate",
    response_model=FieldCacheInvalidationResponse,
)
def invalidate_field_cache(
    request: FieldCacheInvalidationRequest,
):
    """
    Invalidate field-level authorization cache.
    """
    try:
        result = authorization_service.invalidate_field_cache(
            subject_id=request.subject_id,
            role=request.role,
            resource_type=request.resource_type,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Field Cache Clear
# ============================================================


@router.post(
    "/cache/clear",
)
def clear_field_cache():
    """
    Clear all field-level authorization cache entries.
    """
    try:
        result = authorization_service.clear_field_cache()

        return {
            "success": True,
            "message": result
            if isinstance(result, str)
            else "Field authorization cache cleared",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc