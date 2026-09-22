from fastapi import APIRouter, HTTPException, Query

from app.schemas.privacy import (
    DataAccessRequest,
    DataCorrectionRequest,
    ErasureRequest,
    LegalHoldRequest,
    PrivacyInteractionCreate,
    RetentionPolicyCreate,
)
from app.services.privacy import privacy_service


router = APIRouter(
    prefix="/privacy",
    tags=["BE-022 DPDP Privacy"],
)


@router.post("/interactions")
def record_interaction(
    request: PrivacyInteractionCreate,
):
    return privacy_service.record_interaction(
        request
    ).model_dump(mode="json")


@router.post("/data/register")
def register_principal_data(
    tenant_id: str = Query(...),
    principal_id: str = Query(...),
    data: dict = None,
):
    privacy_service.register_principal_data(
        tenant_id=tenant_id,
        principal_id=principal_id,
        data=data or {},
    )

    return {
        "tenant_id": tenant_id,
        "principal_id": principal_id,
        "registered": True,
    }


@router.post("/data/access")
def access_data(
    request: DataAccessRequest,
):
    return privacy_service.access_data(
        tenant_id=request.tenant_id,
        principal_id=request.principal_id,
    ).model_dump(mode="json")


@router.post("/data/correction")
def correct_data(
    request: DataCorrectionRequest,
):
    try:
        return privacy_service.correct_data(
            request
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.post("/retention")
def create_retention_policy(
    request: RetentionPolicyCreate,
):
    return privacy_service.create_retention_policy(
        request
    ).model_dump(mode="json")


@router.post("/legal-hold")
def create_legal_hold(
    request: LegalHoldRequest,
):
    return privacy_service.create_legal_hold(
        request
    ).model_dump(mode="json")


@router.post("/erasure")
def request_erasure(
    request: ErasureRequest,
):
    try:
        return privacy_service.request_erasure(
            request
        ).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/erasure/certificate/{certificate_id}")
def get_erasure_certificate(
    certificate_id: str,
    tenant_id: str = Query(...),
):
    try:
        return privacy_service.get_certificate(
            certificate_id=certificate_id,
            tenant_id=tenant_id,
        ).model_dump(mode="json")
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