from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.repositories.task_repository import task_repository

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
    """Create a task using PostgreSQL or the in-memory service."""
    try:
        if not settings.database_enabled:
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

        if payload.metadata:
            raise ValueError(
                "Non-empty metadata is not supported for PostgreSQL tasks yet."
            )

        if payload.priority == "urgent":
            raise ValueError(
                "Priority 'urgent' is not supported by PostgreSQL tasks; "
                "use low, normal, or high."
            )

        if not all((
            payload.assignee_id,
            payload.creator_assignment_id,
            payload.assignee_node_id,
        )):
            raise ValueError(
                "PostgreSQL task creation requires assignee_id, "
                "creator_assignment_id, and assignee_node_id UUIDs."
            )

        task_id = UUID(payload.task_id)
        creator_id = UUID(payload.created_by)
        assignee_id = UUID(payload.assignee_id)
        creator_assignment_id = UUID(payload.creator_assignment_id)
        assignee_node_id = UUID(payload.assignee_node_id)

        db_priority = {
            "low": "Low",
            "normal": "Medium",
            "high": "High",
        }[payload.priority]

        row = task_repository.create_task(
            task_id=task_id,
            tenant_id=payload.tenant_id,
            title=payload.title,
            description=payload.description,
            creator_id=creator_id,
            creator_assignment_id=creator_assignment_id,
            assignee_id=assignee_id,
            assignee_node_id=assignee_node_id,
            priority=db_priority,
            status="Assigned",
            deadline=payload.due_at,
        )

        return {
            "task_id": str(row["id"]),
            "tenant_id": payload.tenant_id,
            "title": row["title"],
            "description": row.get("description"),
            "created_by": str(row["creator_id"]),
            "assignee_id": str(row["assignee_id"]),
            "priority": {
                "Low": "low",
                "Medium": "normal",
                "High": "high",
            }[row["priority"]],
            "status": "pending",
            "due_at": row.get("deadline"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": {},
        }

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
        if not settings.database_enabled:
            return task_service.search_tasks(
                tenant_id=tenant_id,
                query=query,
                status=status,
                priority=priority,
                assignee_id=assignee_id,
                page=page,
                page_size=page_size,
            )

        parsed_assignee_id = None
        if assignee_id is not None:
            try:
                parsed_assignee_id = UUID(assignee_id)
            except (ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail="assignee_id must be a valid UUID.",
                ) from exc

        result = task_repository.search_tasks(
            tenant_id=tenant_id,
            query=query,
            status=status,
            priority=priority,
            assignee_id=parsed_assignee_id,
            page=page,
            page_size=page_size,
        )

        priority_map = {
            "Low": "low",
            "Medium": "normal",
            "High": "high",
        }
        status_map = {
            "Assigned": "pending",
            "Accepted": "pending",
            "In_Progress": "in_progress",
            "Blocked": "in_progress",
            "Completed": "completed",
            "Rejected": "cancelled",
            "Overdue": "overdue",
        }

        items = []
        for row in result["items"]:
            items.append({
                "task_id": str(row["id"]),
                "tenant_id": tenant_id,
                "title": row["title"],
                "description": row.get("description"),
                "created_by": str(row["creator_id"]),
                "assignee_id": str(row["assignee_id"]),
                "priority": priority_map.get(row["priority"], row["priority"]),
                "status": status_map.get(row["status"], row["status"]),
                "due_at": row.get("deadline"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "metadata": {},
            })

        return {
            "items": items,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }

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
        if settings.database_enabled:
            return task_repository.statistics(
                tenant_id=tenant_id,
            )

        return task_service.statistics(
            tenant_id=tenant_id,
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


# ============================================================
# Task Details
# ============================================================


@router.get("/{task_id}")
def get_task(
    task_id: str,
    tenant_id: str = Query(...),
):
    """Get task details from PostgreSQL or the in-memory service."""
    try:
        if settings.database_enabled:
            try:
                parsed_task_id = UUID(task_id)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="task_id must be a valid UUID in PostgreSQL mode.",
                ) from exc

            row = task_repository.get_task(
                task_id=parsed_task_id,
                tenant_id=tenant_id,
            )

            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail="Task not found",
                )

            priority_map = {
                "Low": "low",
                "Medium": "normal",
                "High": "high",
            }

            status_map = {
                "Assigned": "pending",
                "Accepted": "pending",
                "In_Progress": "in_progress",
                "Blocked": "in_progress",
                "Completed": "completed",
                "Rejected": "cancelled",
                "Overdue": "overdue",
            }

            return {
                "task_id": str(row["id"]),
                "tenant_id": tenant_id,
                "title": row["title"],
                "description": row.get("description"),
                "created_by": str(row["creator_id"]),
                "assignee_id": str(row["assignee_id"]),
                "priority": priority_map.get(
                    row["priority"], row["priority"]
                ),
                "status": status_map.get(
                    row["status"], row["status"]
                ),
                "due_at": row.get("deadline"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": {},
            }

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
    """Update a task using PostgreSQL or the in-memory service."""
    try:
        if not settings.database_enabled:
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

        try:
            parsed_task_id = UUID(task_id)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=400,
                detail="task_id must be a valid UUID in PostgreSQL mode.",
            ) from exc

        if payload.assignee_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Changing assignee is not supported by this PostgreSQL "
                    "endpoint because a new assignment and node are required."
                ),
            )

        if payload.metadata:
            raise HTTPException(
                status_code=400,
                detail="Non-empty metadata is not supported for PostgreSQL tasks.",
            )

        priority_map = {
            "low": "Low",
            "normal": "Medium",
            "high": "High",
        }
        status_map = {
            "pending": "Assigned",
            "in_progress": "In_Progress",
            "completed": "Completed",
            "cancelled": "Rejected",
            "overdue": "Overdue",
        }

        db_priority = None
        if payload.priority is not None:
            if payload.priority not in priority_map:
                raise HTTPException(
                    status_code=400,
                    detail="Priority 'urgent' is not supported for PostgreSQL tasks.",
                )
            db_priority = priority_map[payload.priority]

        db_status = None
        if payload.status is not None:
            if payload.status not in status_map:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported task status for PostgreSQL tasks.",
                )
            db_status = status_map[payload.status]

        row = task_repository.update_task(
            task_id=parsed_task_id,
            tenant_id=tenant_id,
            title=payload.title,
            description=payload.description,
            priority=db_priority,
            status=db_status,
            deadline=payload.due_at,
            update_deadline="due_at" in payload.model_fields_set,
        )

        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": str(row["id"]),
            "tenant_id": tenant_id,
            "title": row["title"],
            "description": row.get("description"),
            "created_by": str(row["creator_id"]),
            "assignee_id": str(row["assignee_id"]),
            "priority": {
                "Low": "low",
                "Medium": "normal",
                "High": "high",
            }[row["priority"]],
            "status": {
                "Assigned": "pending",
                "Accepted": "pending",
                "In_Progress": "in_progress",
                "Blocked": "in_progress",
                "Completed": "completed",
                "Rejected": "cancelled",
                "Overdue": "overdue",
            }.get(row["status"], row["status"]),
            "due_at": row.get("deadline"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": {},
        }

    except HTTPException:
        raise

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