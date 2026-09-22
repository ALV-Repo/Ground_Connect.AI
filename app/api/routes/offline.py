from fastapi import APIRouter, HTTPException, Query

from app.schemas.offline import (
    ConflictResolutionRequest,
    OfflineOperationRequest,
    ScopeRevocationRequest,
    SyncBatchRequest,
)
from app.services.offline import offline_sync_service


router = APIRouter(
    prefix="/offline",
    tags=["BE-021 Offline Sync"],
)


@router.post("/operations", response_model=dict)
def enqueue_operation(
    request: OfflineOperationRequest,
):
    try:
        return offline_sync_service.enqueue(
            request
        ).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/sync", response_model=dict)
def sync_operations(
    request: SyncBatchRequest,
):
    try:
        return offline_sync_service.sync(
            request
        ).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/operations/{operation_id}", response_model=dict)
def get_operation(
    operation_id: str,
    tenant_id: str = Query(...),
):
    try:
        return offline_sync_service.get_operation(
            tenant_id=tenant_id,
            operation_id=operation_id,
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


@router.post("/conflicts/resolve", response_model=dict)
def resolve_conflict(
    request: ConflictResolutionRequest,
):
    try:
        return offline_sync_service.resolve_conflict(
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


@router.post("/scope/revoke", response_model=dict)
def revoke_scope(
    request: ScopeRevocationRequest,
):
    try:
        return offline_sync_service.revoke_scope(
            request
        ).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/stats", response_model=dict)
def queue_stats(
    tenant_id: str = Query(...),
):
    return offline_sync_service.queue_stats(
        tenant_id=tenant_id,
    ).model_dump(mode="json")