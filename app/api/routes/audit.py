from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.schemas.authorization import (
    ADRQueryRequest,
    ADRQueryResponse,
    DenialQueryRequest,
    DenialQueryResponse,
    WhatCanAccessRequest,
    WhatCanAccessResponse,
    WhoCanAccessRequest,
    WhoCanAccessResponse,
)
from app.services.audit import audit_service_layer


router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
)


# ============================================================
# BE-004: Authorization Decision Records
# ============================================================


@router.post(
    "/query",
    response_model=ADRQueryResponse,
)
def query_authorization_decisions(
    request: ADRQueryRequest,
):
    """
    Query Authorization Decision Records (ADR).
    """
    try:
        result = audit_service_layer.query(
            subject_id=request.subject_id,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            decision=request.decision,
            tenant_id=request.tenant_id,
            branch_id=request.branch_id,
            limit=request.limit,
        )

        return {
            "records": result,
            "count": len(result),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Who Can Access
# ============================================================


@router.post(
    "/who-can-access",
    response_model=WhoCanAccessResponse,
)
def who_can_access(
    request: WhoCanAccessRequest,
):
    """
    Find subjects that can access a resource.
    """
    try:
        result = audit_service_layer.who_can_access(
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            tenant_id=request.tenant_id,
            limit=request.limit,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# What Can Access
# ============================================================


@router.post(
    "/what-can-access",
    response_model=WhatCanAccessResponse,
)
def what_can_access(
    request: WhatCanAccessRequest,
):
    """
    Find resources/actions associated with a subject.
    """
    try:
        result = audit_service_layer.what_can_access(
            subject_id=request.subject_id,
            decision=request.decision,
            limit=request.limit,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Denials
# ============================================================


@router.post(
    "/denials",
    response_model=DenialQueryResponse,
)
def list_denials(
    request: DenialQueryRequest,
):
    """
    List authorization denials.
    """
    try:
        result = audit_service_layer.list_denials(
            subject_id=request.subject_id,
            tenant_id=request.tenant_id,
            limit=request.limit,
        )

        return {
            "records": result,
            "count": len(result),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Audit Export
# ============================================================


@router.get(
    "/export",
)
def export_audit_records(
    tenant_id: Optional[str] = None,
):
    """
    Export authorization decision records.

    The underlying audit service performs sensitive-field
    sanitization before returning records.
    """
    try:
        records = audit_service_layer.export_records(
            tenant_id=tenant_id,
        )

        return {
            "records": records,
            "count": len(records),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc