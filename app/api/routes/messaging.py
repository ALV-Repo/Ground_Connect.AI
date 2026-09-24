from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.messages import MessageCreateRequest
from app.services.messaging import messaging_service


router = APIRouter(
    prefix="/messaging",
    tags=["Messaging"],
)


# ============================================================
# BE-007: Message Creation
# ============================================================


@router.post("")
def create_message(
    payload: MessageCreateRequest,
):
    """
    Create a message for propagation.
    """
    try:
        return messaging_service.create_message(
            message_id=payload.message_id,
            tenant_id=payload.tenant_id,
            subject=payload.subject,
            body=payload.body,
            created_by=payload.created_by,
            recipients=[
                recipient.model_dump()
                for recipient in payload.recipients
            ],
            priority=payload.priority,
            expires_at=payload.expires_at,
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


@router.get("/{message_id}")
def get_message(
    message_id: str,
    tenant_id: str = Query(...),
):
    """
    Get a message within its tenant.
    """
    try:
        return messaging_service.get_message(
            message_id=message_id,
            tenant_id=tenant_id,
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


# ============================================================
# BE-008: Blast Radius
# ============================================================


@router.post("/{message_id}/blast-radius")
def calculate_blast_radius(
    message_id: str,
    tenant_id: str = Query(...),
    recipient_ids: list[str] = Query(...),
    max_recipients: int = Query(200000, ge=1, le=200000),
):
    """
    Calculate message blast radius.
    """
    try:
        return messaging_service.calculate_blast_radius(
            tenant_id=tenant_id,
            recipient_ids=recipient_ids,
            max_recipients=max_recipients,
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
# Message Propagation
# ============================================================


@router.post("/{message_id}/propagate")
def propagate_message(
    message_id: str,
    tenant_id: str = Query(...),
    requested_by: str = Query(...),
    stage: str = Query("initial"),
    batch_size: int = Query(1000, ge=1, le=200000),
):
    """
    Start or continue message propagation.
    """
    try:
        return messaging_service.propagate_message(
            message_id=message_id,
            tenant_id=tenant_id,
            requested_by=requested_by,
            stage=stage,
            batch_size=batch_size,
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
# Staged Delivery
# ============================================================


@router.post("/{message_id}/stages")
def start_staged_delivery(
    message_id: str,
    tenant_id: str = Query(...),
    stage_name: str = Query(...),
    batch_size: int = Query(1000, ge=1, le=200000),
    requested_by: str = Query(...),
):
    """
    Start a staged message delivery.
    """
    try:
        return messaging_service.start_staged_delivery(
            message_id=message_id,
            tenant_id=tenant_id,
            stage_name=stage_name,
            batch_size=batch_size,
            requested_by=requested_by,
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


@router.post("/{message_id}/stages/advance")
def advance_stage(
    message_id: str,
    tenant_id: str = Query(...),
    stage_name: str = Query(...),
):
    """
    Advance an existing delivery stage.
    """
    try:
        return messaging_service.advance_stage(
            message_id=message_id,
            tenant_id=tenant_id,
            stage_name=stage_name,
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
# Emergency Halt
# ============================================================


@router.post("/{message_id}/halt")
def halt_delivery(
    message_id: str,
    tenant_id: str = Query(...),
    requested_by: str = Query(...),
    reason: str = Query(...),
):
    """
    Halt message delivery.
    """
    try:
        return messaging_service.halt_delivery(
            message_id=message_id,
            tenant_id=tenant_id,
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


# ============================================================
# Resume Delivery
# ============================================================


@router.post("/{message_id}/resume")
def resume_delivery(
    message_id: str,
    tenant_id: str = Query(...),
    requested_by: str = Query(...),
):
    """
    Resume a halted message delivery.
    """
    try:
        return messaging_service.resume_delivery(
            message_id=message_id,
            tenant_id=tenant_id,
            requested_by=requested_by,
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


# ============================================================
# Delivery Events
# ============================================================


@router.get("/{message_id}/events")
def delivery_events(
    message_id: str,
    tenant_id: str = Query(...),
):
    """
    Get message delivery events.
    """
    try:
        return messaging_service.delivery_events(
            message_id=message_id,
            tenant_id=tenant_id,
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


# ============================================================
# Cancel
# ============================================================


@router.post("/{message_id}/cancel")
def cancel_message(
    message_id: str,
    tenant_id: str = Query(...),
    requested_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    """
    Cancel message propagation.
    """
    try:
        return messaging_service.cancel_message(
            message_id=message_id,
            tenant_id=tenant_id,
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
# Search
# ============================================================


@router.get("")
def search_messages(
    tenant_id: str = Query(...),
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """
    Search messages within a tenant.
    """
    try:
        return messaging_service.search_messages(
            tenant_id=tenant_id,
            query=query,
            status=status,
            priority=priority,
            page=page,
            page_size=page_size,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc