from fastapi import APIRouter, HTTPException, Query

from app.schemas.compliance import (
    ComplianceProfileActivateRequest,
    ComplianceProfileCreate,
)
from app.services.compliance import compliance_service


router = APIRouter(
    prefix="/compliance",
    tags=["BE-023 Compliance"],
)


@router.post("/profiles")
def create_profile(
    request: ComplianceProfileCreate,
):
    return compliance_service.create_profile(
        request
    ).model_dump(mode="json")


@router.post("/profiles/activate")
def activate_profile(
    request: ComplianceProfileActivateRequest,
):
    try:
        return compliance_service.activate_profile(
            request
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


@router.get("/profiles/{profile_id}")
def get_profile(
    profile_id: str,
    tenant_id: str = Query(...),
):
    try:
        return compliance_service.get_profile(
            tenant_id=tenant_id,
            profile_id=profile_id,
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


@router.get("/status")
def get_compliance_status(
    tenant_id: str = Query(...),
):
    return compliance_service.get_status(
        tenant_id=tenant_id,
    ).model_dump(mode="json")