from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.recovery import recovery_service


router = APIRouter(
    prefix="/recovery",
    tags=["HA / Backup / Recovery"],
)


# ============================================================
# BE-016: Backup
# ============================================================


@router.post("/backups")
def create_backup(
    payload: Dict[str, Any],
):
    """
    Create a backup record.
    """
    try:
        return recovery_service.create_backup(
            backup_id=payload.get("backup_id"),
            backup_type=payload.get("backup_type", "full"),
            source=payload.get("source", "application"),
            size_bytes=payload.get("size_bytes", 0),
            checksum=payload.get("checksum"),
            location=payload.get("location"),
            metadata=payload.get("metadata"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/backups/{backup_id}")
def get_backup(
    backup_id: str,
):
    """
    Get backup details.
    """
    try:
        return recovery_service.get_backup(
            backup_id=backup_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/backups")
def list_backups(
    status: Optional[str] = Query(None),
    backup_type: Optional[str] = Query(None),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
):
    """
    List available backups.
    """
    try:
        return {
            "items": recovery_service.list_backups(
                status=status,
                backup_type=backup_type,
                limit=limit,
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Restore
# ============================================================


@router.post("/restore")
def restore_backup(
    payload: Dict[str, Any],
):
    """
    Restore the system from a selected backup.
    """
    try:
        return recovery_service.restore(
            backup_id=payload.get("backup_id"),
            requested_by=payload.get("requested_by"),
            target=payload.get("target", "application"),
            dry_run=payload.get("dry_run", False),
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Recovery Validation
# ============================================================


@router.post("/validate")
def validate_recovery(
    payload: Dict[str, Any],
):
    """
    Validate whether a backup is suitable for recovery.
    """
    try:
        return recovery_service.validate_backup(
            backup_id=payload.get("backup_id"),
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/verify")
def verify_recovery(
    payload: Dict[str, Any],
):
    """
    Verify recovery readiness / recovery test result.
    """
    try:
        return recovery_service.verify_recovery(
            backup_id=payload.get("backup_id"),
            requested_by=payload.get("requested_by"),
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Retention
# ============================================================


@router.post("/retention")
def apply_retention():
    """
    Apply configured backup retention policy.
    """
    try:
        return recovery_service.apply_retention_policy()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# Recovery Events
# ============================================================


@router.get("/events")
def recovery_events(
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
):
    """
    Return recent recovery events.
    """
    try:
        return {
            "items": recovery_service.get_restore_events(
                limit=limit,
            )
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# Recovery Status
# ============================================================


@router.get("/status")
def recovery_status():
    """
    Return HA / backup / recovery status.
    """
    try:
        return recovery_service.get_recovery_status()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get("/rpo-rto")
def rpo_rto_status():
    """
    Return configured Recovery Point Objective
    and Recovery Time Objective.
    """
    try:
        rpo = recovery_service.check_rpo()
        rto = recovery_service.get_rto_target()

        return {
            "rpo": rpo,
            "rto": rto,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# Test Data
# ============================================================


@router.delete("/test-data")
def clear_test_data():
    """
    Clear recovery test data.
    Intended for development/testing workflows.
    """
    try:
        return recovery_service.clear_test_data()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc