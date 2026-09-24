from fastapi import APIRouter, HTTPException, Query

from app.schemas.workflow import (
    DisputeReopenRequest,
    IssueStatusUpdateRequest,
    RejectionRequest,
    SLAConfigCreate,
    WorkflowIssueRegistrationRequest,
)
from app.services.workflow import workflow_service


router = APIRouter(
    prefix="/workflow",
    tags=["BE-019 Citizen Workflow & SLA"],
)


@router.post("/sla", response_model=dict)
def configure_sla(request: SLAConfigCreate):
    return workflow_service.configure_sla(request).model_dump()


@router.post("/issues/{issue_id}/register", response_model=dict)
def register_issue(
    issue_id: str,
    request: WorkflowIssueRegistrationRequest,
):
    try:
        return workflow_service.register_issue(
            issue_id=issue_id,
            tenant_id=request.tenant_id,
            category=request.category,
            priority=request.priority,
        ).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/issues/{issue_id}", response_model=dict)
def get_issue(
    issue_id: str,
    tenant_id: str = Query(...),
):
    try:
        return workflow_service.get_issue(
            issue_id=issue_id,
            tenant_id=tenant_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/issues/status", response_model=dict)
def update_status(request: IssueStatusUpdateRequest):
    try:
        return workflow_service.update_status(request).model_dump(mode="json")
    except (KeyError, ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/issues/reject", response_model=dict)
def reject_issue(request: RejectionRequest):
    try:
        return workflow_service.reject_issue(request).model_dump(mode="json")
    except (KeyError, ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/issues/dispute-reopen", response_model=dict)
def dispute_reopen(request: DisputeReopenRequest):
    try:
        return workflow_service.dispute_reopen(request).model_dump(mode="json")
    except (KeyError, ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/issues/{issue_id}/sla", response_model=dict)
def check_sla(
    issue_id: str,
    tenant_id: str = Query(...),
):
    try:
        return workflow_service.check_sla(
            issue_id=issue_id,
            tenant_id=tenant_id,
        ).model_dump(mode="json")
    except (KeyError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/issues/{issue_id}/escalations", response_model=list)
def get_escalations(
    issue_id: str,
    tenant_id: str = Query(...),
):
    try:
        events = workflow_service.get_escalations(
            issue_id=issue_id,
            tenant_id=tenant_id,
        )
        return [event.model_dump(mode="json") for event in events]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))