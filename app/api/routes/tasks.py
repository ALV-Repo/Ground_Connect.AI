from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

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
    payload: Dict[str, Any],
):
    """
    Create a task.
    """
    try:
        return task_service.create_task(
            task_id=payload.get("task_id"),
            tenant_id=payload.get("tenant_id"),
            title=payload.get("title"),
            description=payload.get("description"),
            created_by=payload.get("created_by"),
            assignee_id=payload.get("assignee_id"),
            priority=payload.get("priority", "normal"),
            due_at=payload.get("due_at"),
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
    tenant_id: str = Query(...),
    payload: Dict[str, Any] | None = None,
):
    """
    Update task information.
    """
    try:
        return task_service.update_task(
            task_id=task_id,
            tenant_id=tenant_id,
            title=(payload or {}).get("title"),
            description=(payload or {}).get("description"),
            assignee_id=(payload or {}).get("assignee_id"),
            priority=(payload or {}).get("priority"),
            due_at=(payload or {}).get("due_at"),
            status=(payload or {}).get("status"),
            metadata=(payload or {}).get("metadata"),
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
    payload: Dict[str, Any],
):
    """
    Add evidence to a task.
    """
    try:
        return task_service.add_evidence(
            evidence_id=payload.get("evidence_id"),
            task_id=task_id,
            uploaded_by=payload.get("uploaded_by"),
            file_name=payload.get("file_name"),
            content_type=payload.get("content_type"),
            size_bytes=payload.get("size_bytes", 0),
            sha256=payload.get("sha256"),
            storage_reference=payload.get("storage_reference"),
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