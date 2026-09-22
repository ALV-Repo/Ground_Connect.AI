from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.schemas.closure import (
    ClosureConfirmationRequest,
    ResolutionProposalRequest,
)
from app.services.closure import closure_service


router = APIRouter(
    prefix="/closure",
    tags=["BE-020 Citizen Verified Closure"],
)


@router.post("/issues/register", response_model=dict)
def register_issue(
    issue_id: str,
    tenant_id: str,
    unit_id: str,
    severity: float = 1.0,
    corroboration_count: int = 0,
    sla_breached: bool = False,
):
    try:
        return closure_service.register_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
            unit_id=unit_id,
            severity=severity,
            corroboration_count=corroboration_count,
            sla_breached=sla_breached,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/units/register", response_model=dict)
def register_unit(
    tenant_id: str,
    unit_id: str,
    unit_size: float,
    intake_volume: float,
):
    try:
        return closure_service.register_unit(
            tenant_id=tenant_id,
            unit_id=unit_id,
            unit_size=unit_size,
            intake_volume=intake_volume,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/proposals", response_model=dict)
def propose_resolution(
    request: ResolutionProposalRequest,
):
    try:
        return closure_service.propose_resolution(
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


@router.post(
    "/proposals/{proposal_id}/confirmation-request",
    response_model=dict,
)
def create_confirmation_request(
    proposal_id: str,
    citizen_id: str,
    language: str,
    wait_minutes: int = 1440,
):
    try:
        return closure_service.create_confirmation_request(
            proposal_id=proposal_id,
            citizen_id=citizen_id,
            language=language,
            wait_minutes=wait_minutes,
        ).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/confirmations", response_model=dict)
def respond_to_confirmation(
    request: ClosureConfirmationRequest,
):
    try:
        return closure_service.respond_to_confirmation(
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
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post(
    "/confirmations/finalize-expired",
    response_model=list,
)
def finalize_expired_confirmations(
    tenant_id: str = Query(...),
):
    try:
        results = closure_service.finalize_expired_confirmations(
            tenant_id=tenant_id,
            now=datetime.now().astimezone(),
        )

        return [
            result.model_dump(mode="json")
            for result in results
        ]
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )


@router.get("/confirmations/{request_id}", response_model=dict)
def get_confirmation_request(
    request_id: str,
    tenant_id: str = Query(...),
):
    try:
        return closure_service.get_confirmation_request(
            request_id=request_id,
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


@router.get("/metrics", response_model=dict)
def closure_metrics(
    tenant_id: str = Query(...),
):
    return closure_service.closure_metrics(
        tenant_id=tenant_id,
    ).model_dump(mode="json")


@router.get("/service-debt/{unit_id}", response_model=dict)
def service_debt_index(
    unit_id: str,
    tenant_id: str = Query(...),
):
    try:
        return closure_service.calculate_service_debt_index(
            tenant_id=tenant_id,
            unit_id=unit_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )