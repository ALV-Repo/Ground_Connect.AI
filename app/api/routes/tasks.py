from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.tasks import (
    EvidenceCreateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)
from app.services.tasks import task_service


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


# ============================================================
# BE-009: Task Engine
# ============================================================


@router.post("")
def create_task(
    payload: TaskCreateRequest,
):
    """
    Create a task.
    """
    try:
        return task_service.create_task(
            task_id=payload.task_id,
            tenant_id=payload.tenant_id,
            title=payload.title,
            description=payload.description,
            created_by=payload.created_by,
            assignee_id=payload.assignee_id,
            priority=payload.priority,
            due_at=payload.due_at,
            metadata=payload.metadata,
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


# ============================================================
# Search
# ============================================================


@router.get("/search")
def search_tasks(
    tenant_id: str = Query(...),
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """
    Search tasks within a tenant.
    """
    try:
        return task_service.search_tasks(
            tenant_id=tenant_id,
            query=query,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            page=page,
            page_size=page_size,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Statistics
# ============================================================


@router.get("/statistics/summary")
def task_statistics(
    tenant_id: str = Query(...),
):
    """
    Return task statistics for a tenant.
    """
    try:
        return task_service.statistics(
            tenant_id=tenant_id,
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


# ============================================================
# Task Details
# ============================================================


@router.get("/{task_id}")
def get_task(
    task_id: str,
    tenant_id: str = Query(...),
):
    """
    Get task details.
    """
    try:
        task = task_service.get_task(
            task_id=task_id,
            tenant_id=tenant_id,
        )

        if task is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return task

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    tenant_id: str = Query(...),
):
    """
    Update task information.
    """
    try:
        return task_service.update_task(
            task_id=task_id,
            tenant_id=tenant_id,
            title=payload.title,
            description=payload.description,
            assignee_id=payload.assignee_id,
            priority=payload.priority,
            due_at=payload.due_at,
            status=payload.status,
            metadata=payload.metadata,
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
# Task Actions
# ============================================================


@router.post("/{task_id}/actions")
def task_action(
    task_id: str,
    action: str = Query(...),
    tenant_id: str = Query(...),
    requested_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    """
    Execute a task lifecycle action.
    """
    try:
        return task_service.task_action(
            task_id=task_id,
            tenant_id=tenant_id,
            action=action,
            requested_by=requested_by,
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
# Evidence
# ============================================================


@router.post("/{task_id}/evidence")
def add_evidence(
    task_id: str,
    payload: EvidenceCreateRequest,
):
    """
    Add evidence to a task.
    """
    try:
        return task_service.add_evidence(
            evidence_id=payload.evidence_id,
            task_id=task_id,
            uploaded_by=payload.uploaded_by,
            file_name=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256,
            storage_reference=payload.storage_reference,
            metadata=payload.metadata,
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


@router.get("/{task_id}/evidence")
def list_evidence(
    task_id: str,
):
    """
    List evidence attached to a task.
    """
    try:
        return task_service.list_evidence(
            task_id=task_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/{task_id}/evidence/{evidence_id}")
def get_evidence(
    task_id: str,
    evidence_id: str,
):
    """
    Get a specific evidence record.
    """
    try:
        evidence = task_service.get_evidence(
            evidence_id=evidence_id,
            task_id=task_id,
        )

        if evidence is None:
            raise HTTPException(
                status_code=404,
                detail="Evidence not found",
            )

        return evidence

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post("/{task_id}/evidence/{evidence_id}/verify")
def verify_evidence(
    task_id: str,
    evidence_id: str,
    verified_by: str = Query(...),
    expected_sha256: Optional[str] = Query(None),
):
    """
    Verify evidence integrity.
    """
    try:
        evidence = task_service.get_evidence(
            evidence_id=evidence_id,
            task_id=task_id,
        )

        if evidence is None:
            raise HTTPException(
                status_code=404,
                detail="Evidence not found",
            )

        return task_service.verify_evidence(
            evidence_id=evidence_id,
            verified_by=verified_by,
            expected_sha256=expected_sha256,
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